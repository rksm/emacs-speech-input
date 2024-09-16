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
      in
        {

          devShells.default = pkgs.mkShell {
            packages = with pkgs; [
              python
              zlib
            ];

            nativeBuildInputs = with pkgs; [
              pythonPackages.venvShellHook
              emacs-nox
              libsndfile
              libsoundio
              fftw
              blas
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
