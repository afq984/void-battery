{ pkgs ? import <nixpkgs> {} }:

(pkgs.buildFHSUserEnv {
  name = "bazel-userenv-example";
  targetPkgs = pkgs: [
    pkgs.bash
    pkgs.virtualenv
    pkgs.go
    pkgs.meson
    pkgs.cmake
    pkgs.ninja
    pkgs.pkg-config
    pkgs.libsodium
    pkgs.simde
    pkgs.libunistring
    pkgs.gcc
    pkgs.black
  ];
  extraOutputsToInstall = [ "dev" ];
}).env
