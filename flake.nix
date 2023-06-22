{
  description = "Application packaged using poetry2nix";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.poetry2nix.url = "github:nix-community/poetry2nix";

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    {
      # Nixpkgs overlay providing the application
      overlay = nixpkgs.lib.composeManyExtensions [
        poetry2nix.overlay
        (final: prev: {
          # The application
          myapp = prev.poetry2nix.mkPoetryApplication {
            projectDir = ./.;
            overrides = 
            let
              overrideInputs = buildInputs: nativeBuildInputs: oldAttrs: {
                buildInputs = oldAttrs.buildInputs ++ buildInputs;
                nativeBuildInputs = oldAttrs.nativeBuildInputs ++ [ prev.python3Packages.setuptools ] ++ nativeBuildInputs;
              };
              cairo = prev.cairo;
              pkg-config = prev.pkg-config;
              gobject-introspection = prev.gobject-introspection;
            in prev.poetry2nix.overrides.withoutDefaults (final2: prev2: {
              pycairo = prev2.pycairo.overrideAttrs (overrideInputs [ cairo ] [ pkg-config ]);

              pygobject = prev2.pygobject.overrideAttrs (overrideInputs [ cairo ] [ pkg-config gobject-introspection ]);

              asyncio-glib = prev2.asyncio-glib.overrideAttrs (overrideInputs [] []);

              gbulb = prev2.gbulb.overrideAttrs (overrideInputs [] []);

              dasbus = prev2.dasbus.overrideAttrs (overrideInputs [] []);

              indexed = prev2.indexed.overrideAttrs (overrideInputs [] []);
            });
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
        apps = {
          myapp = pkgs.myapp;
        };

        defaultApp = pkgs.myapp;

        devShell = with pkgs; mkShell {
          inputsFrom = [ defaultApp ];
          buildInputs = [ gtk4 gobject-introspection libdbusmenu ];
          packages = [ nodePackages.pyright poetry jetbrains.pycharm-community ];
          shellHook = ''
            export PYTHONPATH=$PYTHONPATH:$PWD
            export XDG_DATA_DIRS=$XDG_DATA_DIRS:/etc/profiles/per-user/$USER/share
          '';
        };
      }));
}
