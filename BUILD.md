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

## How to Contribute to This Project

---

This project is open-source and welcomes contributions.
For detailed information on how to contribute, please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file.
