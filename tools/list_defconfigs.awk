function print_config(marker, description)
{
    if (config_file == "")
        return

    # BOARD_K230_CANMV is the default Kconfig choice and may be omitted.
    if (board == "")
        board = "BOARD_K230_CANMV"

    marker = (config_name == current) ? "*" : " "
    description = defconfig_descriptions[config_name]
    if (description == "")
        description = board_descriptions[board]
    if (description == "")
        description = board

    printf "%d [%s] %-44s -- %s\n", ++config_number, marker, config_name, description
}

# The first input is boards/Kconfig. Collect each board choice's prompt.
FILENAME == ARGV[1] {
    if ($1 == "config") {
        board_key = $2
    } else if (board_key ~ /^BOARD_/ && $1 == "bool" && index($0, "\"") != 0) {
        description = $0
        sub(/^[^"]*"/, "", description)
        sub(/".*$/, "", description)
        board_descriptions[board_key] = description
        board_key = ""
    }
    next
}

# The second input contains optional descriptions for specific defconfigs.
FILENAME == ARGV[2] {
    if ($0 ~ /^[ \t]*(#|$)/)
        next

    separator = index($0, "|")
    if (separator == 0)
        next

    config_name = substr($0, 1, separator - 1)
    description = substr($0, separator + 1)
    defconfig_descriptions[config_name] = description
    next
}

FILENAME != config_file {
    print_config()
    config_file = FILENAME
    config_name = FILENAME
    sub(/^.*\//, "", config_name)
    board = ""
}

/^CONFIG_BOARD_[A-Z0-9_]+=y$/ {
    board = $0
    sub(/^CONFIG_/, "", board)
    sub(/=y$/, "", board)
}

END {
    print_config()
}
