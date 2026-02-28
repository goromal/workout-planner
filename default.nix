{
  buildPythonPackage,
  setuptools,
  lib,
  click,
  pyyaml,
  anthropic,
  easy-google-auth
}:
buildPythonPackage rec {
  pname = "REPLACEME";
  version = "0.0.0";
  pyproject = true;
  build-system = [ setuptools ];
  src = lib.cleanSource ./.;
  propagatedBuildInputs = [
    pyyaml
    click
    anthropic
    easy-google-auth
  ];
  doCheck = false;
}
