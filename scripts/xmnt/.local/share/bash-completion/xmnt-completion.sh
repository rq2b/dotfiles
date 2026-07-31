_xmnt() {
    COMPREPLY=()
    local cur="${COMP_WORDS[COMP_CWORD]}"

    case "${COMP_CWORD}" in
        1)
            COMPREPLY=($(compgen -W "data vm all both persistent mount umount open close list status doctor help" -- "$cur"))
            ;;
        2)
            case "${COMP_WORDS[1]}" in
                mount|umount)
                    COMPREPLY=($(compgen -W "data vm all both persistent" -- "$cur"))
                    ;;
                status)
                    COMPREPLY=($(compgen -W "--verbose -v" -- "$cur"))
                    ;;
            esac
            ;;
    esac
}

complete -F _xmnt xmnt
