with import <nixpkgs> {};

stdenv.mkDerivation rec {
  name = "wl100";
  env = buildEnv { name = name; paths = buildInputs; };
  buildInputs = [
    (python38.withPackages (pypkgs: [ pypkgs.pip pypkgs.virtualenv ]))
    pipenv
  ];
  shellHook = ''
    # set SOURCE_DATE_EPOCH so that we can use python wheels
    SOURCE_DATE_EPOCH=$(date +%s)
  '';
}

