{
  description = "Application packaged using poetry2nix";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    {
      # Nixpkgs overlay providing the application
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlays.default
        (final: prev: {
          # The application
          driveicon = prev.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
          };
        })
      ];
    } // (flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [ self.overlay ];
        };
      in
      rec {
        defaultApp = pkgs.driveicon;

        devShell = with pkgs; mkShell {
          inputsFrom = [ defaultApp ];
          buildInputs = [ gtk4 gobject-introspection libdbusmenu ];
          packages = [ pyright poetry ninja pkg-config ];
          shellHook = ''
            export PYTHONPATH=$PYTHONPATH:$PWD
            export XDG_DATA_DIRS=$XDG_DATA_DIRS:/etc/profiles/per-user/$USER/share
          '';
        };
      }));
}
