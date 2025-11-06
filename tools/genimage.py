import os
import sys
import argparse

from genimage_py import GenImageTool

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rootpath', required=True)
    parser.add_argument('--outputpath', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()

    tool = GenImageTool(args.rootpath, args.outputpath, args.config)
    tool.run()

if __name__ == "__main__":
    main()
