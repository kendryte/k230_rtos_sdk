#!/bin/bash

source ${SDK_SRC_ROOT_DIR}/.config

gen_repo_info()
{
	pushd ${SDK_SRC_ROOT_DIR} > /dev/null

	input_data=`repo info`
	temp_file=${SDK_BUILD_DIR}/repo_info.tmp

	> $temp_file
	# Process the input data
	echo "$input_data" | awk '
	/^Project:/ {project=$2}
	/Current revision:/ {
		revision=$3
		# Extract last segment of the project path
		split(project, parts, "/")
		last_segment=parts[length(parts)]
		print last_segment "=" revision >> "'$temp_file'"
	}'

	sed 's/-/_/g' $temp_file > $repo_info_file

    echo "Build time $(date)" >> $repo_info_file

	popd > /dev/null
}

gen_image()
{
	local config="$1";
	local image="$2";

    python3 ${SDK_TOOLS_DIR}/genimage.py --rootpath "${SDK_BUILD_IMAGES_DIR}" --outputpath "${SDK_BUILD_DIR}" --config "${config}"

    # Find the generated image file (could be .img or .kdimg)
    generated_image=$(find ${SDK_BUILD_DIR} -maxdepth 1 -type f \( -name "sysimage-sdcard.kdimg" -o -name "sysimage-sdcard.img" -o -name "sysimage-spinand.kdimg" -o -name "sysimage-spinor.kdimg"  \) | head -n 1)

    if [ -z "$generated_image" ]; then
        echo "Error: No generated image file found!"
        exit 1
    fi

    # Get just the filename without path
    generated_image_name=$(basename "$generated_image")

    # Get the file extension
    extension="${generated_image_name##*.}"

    # Rename the file
    mv "$generated_image" "${SDK_BUILD_DIR}/${image}.${extension}"

    echo "Compress image ${image}.${extension}.gz, it will take a while"

    gzip -k -f "${SDK_BUILD_DIR}/${image}.${extension}"
    chmod a+rw "${SDK_BUILD_DIR}/${image}.${extension}" "${SDK_BUILD_DIR}/${image}.${extension}.gz"
    md5sum "${SDK_BUILD_DIR}/${image}.${extension}" "${SDK_BUILD_DIR}/${image}.${extension}.gz" > "${SDK_BUILD_DIR}/${image}.${extension}.gz.md5"

    echo "Generated image done, at ${SDK_BUILD_DIR}/${image}.${extension}"
}

gen_ota_image()
{
    local config="$1";
    local image="$2";

    # 如果没有对应的 kdimage 配置文件，则直接返回
    if [ ! -f "${config}" ]; then
        return
    fi

    echo "Generate kdimage by config ${config}"

    # 清理上一次生成的 *.kdimg，避免被 find 误选
    rm -f ${SDK_BUILD_DIR}/*.kdimg 2>/dev/null || true

    python3 ${SDK_TOOLS_DIR}/genimage.py --rootpath "${SDK_BUILD_IMAGES_DIR}" --outputpath "${SDK_BUILD_DIR}" --config "${config}"

    # 只寻找 kdimg（文件名由 cfg 中的 image 名决定，这里不依赖固定前缀）
    generated_image=$(find ${SDK_BUILD_DIR} -maxdepth 1 -type f -name "*.kdimg" | head -n 1)

    if [ -z "$generated_image" ]; then
        echo "Error: No kdimg image file found for config ${config}!"
        return
    fi

    generated_image_name=$(basename "$generated_image")

    #cp $generated_image ${SDK_BUILD_IMAGES_DIR}/sdcard/
    mv "$generated_image" "${SDK_BUILD_DIR}/${image}.kdimg"

    echo "Compress kdimage ${image}.kdimg.gz, it will take a while"

    gzip -k -f "${SDK_BUILD_DIR}/${image}.kdimg"
    chmod a+rw "${SDK_BUILD_DIR}/${image}.kdimg" "${SDK_BUILD_DIR}/${image}.kdimg.gz"
    md5sum "${SDK_BUILD_DIR}/${image}.kdimg" "${SDK_BUILD_DIR}/${image}.kdimg.gz" > "${SDK_BUILD_DIR}/${image}.kdimg.gz.md5"

    echo "Generated kdimage done, at ${SDK_BUILD_DIR}/${image}.kdimg"
}

parse_repo_version()
{
    pushd "${SDK_CANMV_SRC_DIR}" > /dev/null

    # Get the revision and store it in a variable
    revision=$(git describe --long --tag --dirty --always)

    popd > /dev/null

    # Print the revision to be captured by the caller
    echo "$revision"
}

parse_nncase_version()
{
    # Extract the version from the header file
    VERSION=$(grep -oP '(?<=#define NNCASE_VERSION ")[^"]*' ${SDK_RTSMART_SRC_DIR}/libs/nncase/riscv64/nncase/include/nncase/version.h)

    echo "$VERSION"
}

# generate nncase version
nncase_version=$(parse_nncase_version)

repo_info_file=${SDK_BUILD_DIR}/repo_info
gen_repo_info
cp -f $repo_info_file ${SDK_BUILD_IMAGES_DIR}/sdcard/revision.txt

# Read the file line by line
while IFS='=' read -r key value; do
  # Skip empty lines or lines that don't contain '='
  if [ -z "$key" ] || [ -z "$value" ]; then
    continue
  fi

  # Assign the value to the variable
  eval "$key=\"$value\""

  # Print the variable to verify
  echo "Repo '$key' commit is '${!key}'"
done < "$repo_info_file"

# Delete kmodels if running in CI
if [ "$IS_CI" = "2" ]; then
    mkdir -p ${SDK_BUILD_IMAGES_DIR}/sdcard/examples/kmodel/
    rm -rf ${SDK_BUILD_IMAGES_DIR}/sdcard/examples/kmodel/*

    output_file="${SDK_BUILD_IMAGES_DIR}/sdcard/README.txt"
    cat <<EOF > "$output_file"
请从网络下载模型文件并解压，将“ai_poc/kmodel”下的模型文件复制到SDCARD分区的“examples/kmodel”目录
Please download the model file from the Internet and decompress it. Copy the model file under "ai_poc/kmodel" to the "examples/kmodel" directory of the SDCARD partition.
下载地址为https://kendryte-download.canaan-creative.com/k230/downloads/kmodel/kmodel_v$nncase_version.tgz
EOF
fi

# generate image name
if [ "$IS_CI" = "1" ] || [ "$IS_CI" = "2" ]; then
    if [ "$CONFIG_SDK_ENABLE_CANMV" = "y" ]; then
        canmv_revision=$(parse_repo_version ${SDK_CANMV_SRC_DIR})
        image_name="${MK_IMAGE_NAME}_micropython_PreRelease_nncase_v${nncase_version}"
    else
        rtsmart_revision=$(parse_repo_version ${SDK_RTSMART_SRC_DIR})
        image_name="${MK_IMAGE_NAME}_rtsmart_PreRelease_nncase_v${nncase_version}"
    fi
else
    if [ "$CONFIG_SDK_ENABLE_CANMV" = "y" ]; then
        if [ -z "$CI" ]; then
            canmv_revision="local"
        else
            canmv_revision=$(parse_repo_version ${SDK_CANMV_SRC_DIR})
        fi
        echo "canmv_revision '${canmv_revision}'"
        image_name="${MK_IMAGE_NAME}_micropython_${canmv_revision}_nncase_v${nncase_version}"
    else
        if [ -z "$CI" ]; then
            rtsmart_revision="local"
        else
            rtsmart_revision=$(parse_repo_version ${SDK_RTSMART_SRC_DIR})
        fi
        image_name="${MK_IMAGE_NAME}_rtsmart_${rtsmart_revision}_nncase_v${nncase_version}"
    fi
fi

gen_ota_image "${SDK_BOARD_DIR}/genimage-sdcard-ota.cfg" "${image_name}_ota"
gen_image ${SDK_BOARD_DIR}/${CONFIG_BOARD_GEN_IMAGE_CFG_FILE} $image_name;
