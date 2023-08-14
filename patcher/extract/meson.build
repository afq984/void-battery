project(
    'extract',
    'cpp',
    default_options: ['warning_level=0', 'cpp_std=c++17'],
)

cmake = import('cmake')

ooz = cmake.subproject('ooz')

exe = executable(
    'extract',
    'extract.cpp',
    install: true,
    dependencies: [
        ooz.dependency('libbun'),
        ooz.dependency('libooz'),
    ],
)
