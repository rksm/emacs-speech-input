#!/usr/bin/env -S nix develop . -c python

import os
import queue
import sys
import threading
from contextlib import suppress

# Use PulseAudio/PipeWire for audio
os.environ['PULSE_LATENCY_MSEC'] = '30'

import pyaudio
from deepgram import DeepgramClient


CHANNELS = 1
CHUNK = 1024
FORMAT = pyaudio.paInt16
SAMPLE_RATE = 16000


def result_to_json(result):
    if hasattr(result, "model_dump_json"):
        return result.model_dump_json(exclude_none=True)
    if hasattr(result, "json"):
        return result.json()
    return str(result)


def get_transcript(result):
    try:
        alternatives = result.channel.alternatives
        if alternatives:
            return alternatives[0].transcript
    except AttributeError:
        return ""
    return ""


def on_message(result):
    sentence = result.channel.alternatives[0].transcript

    if len(sentence) == 0:
        return

    print(f"Output: {result_to_json(result)}", flush=True)


def on_metadata(metadata):
    print(f"\n\n{result_to_json(metadata)}\n\n", flush=True)


def on_speech_started(speech_started):
    print(f"\n\n{result_to_json(speech_started)}\n\n", flush=True)


def on_utterance_end(utterance_end):
    print(f"\n\n{result_to_json(utterance_end)}\n\n", flush=True)


def handle_message(message):
    message_type = getattr(message, "type", None)

    if message_type == "Results":
        if get_transcript(message):
            on_message(message)
    elif message_type == "Metadata":
        on_metadata(message)
    elif message_type == "SpeechStarted":
        on_speech_started(message)
    elif message_type == "UtteranceEnd":
        on_utterance_end(message)
    else:
        print(f"\n\n{message}\n\n", flush=True)


def receive_messages(connection, stop_event):
    try:
        for message in connection:
            if stop_event.is_set():
                break
            handle_message(message)
    except Exception as exc:
        if not stop_event.is_set():
            print(f"Deepgram receive error: {exc}", file=sys.stderr, flush=True)
            stop_event.set()


def send_audio(connection, audio_queue, stop_event):
    while not stop_event.is_set():
        try:
            audio = audio_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        try:
            connection.send_media(audio)
        except Exception as exc:
            if not stop_event.is_set():
                print(f"Deepgram send error: {exc}", file=sys.stderr, flush=True)
                stop_event.set()
            break


def wait_for_enter(stop_event):
    line = sys.stdin.readline()
    if line:
        stop_event.set()


def open_microphone(audio, audio_queue, stop_event):
    def callback(in_data, frame_count, time_info, status):
        if status:
            print(f"PyAudio status: {status}", file=sys.stderr, flush=True)

        if stop_event.is_set():
            return (None, pyaudio.paComplete)

        with suppress(queue.Full):
            audio_queue.put_nowait(in_data)

        return (None, pyaudio.paContinue)

    return audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK,
        stream_callback=callback,
    )


def main():
    api_key = os.getenv("DG_API_KEY") or os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("DG_API_KEY or DEEPGRAM_API_KEY must be set.", file=sys.stderr, flush=True)
        return 1

    audio = pyaudio.PyAudio()
    stream = None
    stop_event = threading.Event()
    audio_queue = queue.Queue(maxsize=64)

    try:
        deepgram = DeepgramClient(api_key=api_key)

        language = os.getenv("DG_LANGUAGE", "en-IN")
        model = "nova-3" if language in ("en-IN", "multi") else "nova-2"

        with deepgram.listen.v1.connect(
            model=model,
            punctuate=True,
            language=language,
            encoding="linear16",
            channels=CHANNELS,
            sample_rate=SAMPLE_RATE,
            # To get UtteranceEnd, the following must be set:
            interim_results=True,
            utterance_end_ms="1000",
            vad_events=True,
        ) as dg_connection:
            receiver = threading.Thread(
                target=receive_messages,
                args=(dg_connection, stop_event),
                daemon=True,
            )
            sender = threading.Thread(
                target=send_audio,
                args=(dg_connection, audio_queue, stop_event),
                daemon=True,
            )
            input_watcher = threading.Thread(target=wait_for_enter, args=(stop_event,), daemon=True)

            stream = open_microphone(audio, audio_queue, stop_event)
            receiver.start()
            sender.start()
            stream.start_stream()

            print("Press Enter to stop recording...\n", flush=True)
            input_watcher.start()

            while not stop_event.wait(0.1):
                pass

            stop_event.set()
            with suppress(Exception):
                stream.stop_stream()
            with suppress(Exception):
                dg_connection.send_finalize()
            with suppress(Exception):
                dg_connection.send_close_stream()

            sender.join(timeout=2)
            receiver.join(timeout=2)

    except Exception as e:
        print(f"Could not open socket: {e}")
        return 1
    finally:
        stop_event.set()
        if stream is not None:
            with suppress(Exception):
                stream.stop_stream()
            with suppress(Exception):
                stream.close()
        audio.terminate()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
