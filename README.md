# Application

Application layer for PythonEDA applications.

## How to declare it in your flake

Check the latest tag of the artifact repository: https://github.com/pythoneda-shared-pythoneda/application-artifact/tags, and use it instead of the `[version]` placeholder below.

```nix
{
  description = "[..]";
  inputs = rec {
    [..]
    pythoneda-shared-pythoneda-application = {
      [optional follows]
      url =
        "github:pythoneda-shared-pythoneda/application-artifact/[version]?dir=application";
    };
  };
  outputs = [..]
};
```

Should you use another PythonEDA modules, you might want to pin those also used by this project. The same applies to nixos/nixpkgs and flake-utils.
The Nix flake is under the `application` folder of https://github.com/pythoneda-shared-pythoneda/application-artifact.

