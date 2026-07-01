{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      pkgs = import nixpkgs { inherit system; };
      pythonPackages = pkgs.python312Packages;
      python = pkgs.python312;
      emacs = (pkgs.emacsPackagesFor pkgs.emacs-nox).emacsWithPackages (epkgs: with epkgs; [
        buttercup
        dash
        f
        llm
        s
      ]);
    in
    {

      devShells.default = pkgs.mkShell {
        packages = with pkgs; [
          python
          zlib
          jack2
        ];

        nativeBuildInputs = with pkgs; [
          pythonPackages.venvShellHook
          emacs
          libsndfile
          libsoundio
          fftw
          blas
          cmocka
          ffmpeg-headless
          portaudio
          pkg-config
        ];

        venvDir = ".venv";

        postVenvCreation = ''
          unset SOURCE_DATE_EPOCH
          pip install -r requirements.txt
        '';

        LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
          pkgs.zlib
          pkgs.stdenv.cc.cc
        ];
      };
    }
    );
}
