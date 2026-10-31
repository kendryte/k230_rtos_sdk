# Build Instructions

## Requirements

---

### Compilation  Requirements

Ensure your system has all the necessary packages installed:

```bash
sudo apt-get install -y --no-install-recommends make autoconf automake bison flex gcc g++ \
gawk libncurses5-dev pkg-config libconfuse-dev libssl-dev python3 python3-pip python-is-python3 \
cmake libyaml-dev scons mtools bzip2 curl git openssh-client rsync dosfstools ca-certificates
```

Additionally, install Python packages using `pip`:

```bash
pip3 install pycryptodome gmssl scons==3.1.2
```

### Repository Requirements

To manage the source code, you need to install the `repo` tool:

1. Create a directory for the `repo` binary and add it to your `PATH`:

   ```bash
   mkdir -p ~/.bin
   export PATH="${HOME}/.bin:${PATH}"
   ```

2. Download the `repo` script and make it executable:

   ```bash
   curl https://storage.googleapis.com/git-repo-downloads/repo > ~/.bin/repo
   chmod a+rx ~/.bin/repo
   ```

3. Persist the `PATH` change by adding it to your shell configuration file (e.g., `~/.bashrc`):

   ```bash
   echo 'export PATH="${HOME}/.bin:${PATH}"' >> ~/.bashrc
   source ~/.bashrc
   ```

## Building the Project

---

### Get the Source Code

Initialize and sync the repository to get download the source code:

```bash
# from github with https
repo init -u https://github.com/canmv-k230/manifest -b master --repo-url=https://github.com/canmv-k230/git-repo.git

# or from gitee with ssh, need setup your ssh key
repo init -u git@gitee.com:canmv-k230/manifest.git -b master --repo-url=git@gitee.com:canmv-k230/git-repo.git

repo sync
```

### Build for a Specific Board

1. **Download the toolchain** (only required for the first build):

   ```bash
   make dl_toolchain
   ```

2. **Select a configuration** for your board:

   ```bash
   make list-def
   ```

   The terminal selector groups configurations by firmware type and chip. Use
   Left/Right to choose Arduino, CanMV, or RT-Smart, Tab to choose K230 or K230D,
   Up/Down to choose a board, and Enter to apply the selected defconfig. You can
   open a filtered selector with, for example,
   `make list-def TYPE=rtos CHIP=k230d`.

   In a non-interactive terminal, `make list-def` prints the grouped list without
   changing the current configuration. The selector supports Python 2.7 and
   Python 3; use `make list-def PYTHON=python2` when Python 2 is required.

3. **Alternatively, apply a configuration directly**:

   ```bash
   make k230_canmv_defconfig  # Replace with the appropriate defconfig for your board
   ```

4. **Start the build process**:

   ```bash
   time make log
   ```

This process will compile the software tailored to your selected board configuration.

### Build from an Output Directory

Selecting a defconfig creates `output/<defconfig>/Makefile`. That directory owns
its `.config`, `.config.old`, generated `include/`, and build artifacts. The
root `.config`, `.config.old`, and `include` are symlinks to the selected output.

```bash
make k230_rtos_evb_defconfig
make -C output/k230_rtos_evb_defconfig
make -C output/k230_rtos_evb_defconfig menuconfig
make -C output/k230_rtos_evb_defconfig arduino-sdk
```

Arduino SDK files are generated in `output/<defconfig>/arduino-sdk/`.

To resume another configured output, run `make -C output/<defconfig>` or change
into that directory and run `make`. This restores its saved configuration without
reapplying the defconfig. Running `make <defconfig>` explicitly resets that
output's configuration to the defaults. Run configuration and build commands
separately.

The shared SDK header stays in `output/<defconfig>/include/generated/autoconf.h`.
U-Boot's `sdk_autoconf.h` and the RT-Smart/MPP `k_autoconf_comm.h` aliases are
relative symlinks to that header, updated under the build lock when selecting an
output. OpenSBI reads it through the root `include` symlink. Header copies are
not stored in the RT-Smart cache. Arduino SDK exports copy the header contents
so they remain usable independently of this checkout.

RT-Smart's own BSP configuration and generated headers, SCons signatures,
and generated MPP archives are saved in each output's `rtsmart/.source-state/`. The build
dispatcher restores the files still needed in the source tree with their original
timestamps when switching outputs. Switching back therefore reuses the output's
objects instead of regenerating configuration and recompiling all dependents.
An older output without saved RT-Smart state needs one configuration/build pass
to populate it. Actual configuration or source changes still rebuild dependents.
Shipped MPP archives tracked by the public repository are preserved, including
when selecting an output without a cache. A failed output switch restores the
previous shared files and configuration links before returning an error.

FFmpeg builds in `output/<defconfig>/rtsmart/mpp/middleware/ffmpeg/`, including
its objects, dependency files and compiler-option stamp. Each output needs one
initial FFmpeg build after migrating from the shared source-tree build; later
output switches reuse it. Installing FFmpeg headers preserves their timestamps
so unchanged headers do not rebuild dependent middleware.

FFmpeg uses the checked-in K230 preset by default. After selecting the SDK output,
`make -C src/rtsmart/mpp/middleware/src/ffmpeg/src config` runs configure into that
output's `.sdk-config/` directory. `FFMPEG_CONFIGURATION` can supply configure
options. Run configuration separately from compilation; a failed configure keeps
the previous configuration. FFmpeg `clean` preserves this selection, while its
`distclean` returns to the checked-in preset. The source preset is never rewritten.

Builds synchronize changed Kconfig definitions before loading build options.
A failed defconfig restores the saved configuration and keeps the previous
output selected. `make help` and a non-interactive `make list-def` do not change
the active output. `make -n` reports the output and delegated make command
without running sub-builds or changing configuration links.

`make log` writes `output/<defconfig>/log.txt` and returns a failure if the build
fails. A full `make` clears the selected output's `images/` directory first, so
disabled components and applications leave no stale files in the image.
Component builds such as `make uboot` preserve other components' staged images;
use `make rm_image` to clear `images/` explicitly. `make arduino-sdk-clean` removes the selected output's exported
U-Boot and OpenSBI variants.

`make clean` removes build artifacts while preserving the SDK configuration and
the active RT-Smart BSP configuration, including `rtconfig.h`, SDK configuration
headers and the configuration marker. A rebuild of the same configuration reuses
those settings.
`make distclean` also removes the selected output directory and the active BSP
configuration. Neither command reverts changes saved in board defconfig files.

MMC images configured with `hdimage` also generate a `.kdimg` by default.
KDIMG does not support extended or logical partitions. If a board uses
`extended-partition`, set `kdimage = false` inside its `hdimage` block to disable
KDIMG generation and build only the raw image.

SPI flash physical partition sizes must match the board's runtime partition
table and the KDIMG partition limits. On the EVB, SPI NAND mounts 20 MiB for
`/bin` and 60 MiB for `/sdcard`, while the factory UFFS images contain 10 MiB and
50 MiB of page data respectively, plus OOB metadata. The smaller images leave
room for the writer to skip bad blocks within each physical partition. Factory
flashing erases the full partition so the unwritten tail contains no stale UFFS
nodes. The writer must stop at the partition limit if there are not enough good
blocks. UFFS scans the full physical partition and handles bad blocks through
the NAND MTD driver; it does not require a separate FTL. This image margin is not
a permanently reserved pool: UFFS can use the remaining good blocks at runtime.

SPI NOR uses 4 MiB for `/bin` and 12 MiB for `/sdcard`. JFFS2 compresses file
contents, but reported capacity is still the physical partition size. Its used
space includes compressed data and filesystem metadata; padded image size is
not used space.

For an existing checkout, `make outputmakefile` migrates the current root
configuration and generated headers into its output directory, preserving file
contents and timestamps. It creates the forwarding Makefile without compiling
firmware. Other old outputs need their matching configuration initialized before
they can be resumed; the current root configuration is migrated only to its own
output.

The shared root links allow one active SDK build at a time; a second independent
build is rejected while the first is running. Switching outputs preserves object
caches, but the shared RT-Smart BSP configuration is regenerated on its next
build. Dependencies affected by that configuration can still be rebuilt.

## How to Contribute to This Project

---

This project is open-source and welcomes contributions.
For detailed information on how to contribute, please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file.
