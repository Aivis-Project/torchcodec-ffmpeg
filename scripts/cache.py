import torchcodec_components
from pkg import all_packages


def main():
    with open("cache.txt", "w") as file:
        # torchcodec-ffmpeg: also key the cache on the packages of
        # torchcodec_components
        # for package in sorted(all_packages):
        for package in sorted(all_packages + torchcodec_components.EXTRA_PACKAGES):
            file.write(f"{package.name}:{package.sha256}\n")

if __name__ == "__main__":
    main()

