export WORK="$HOME"/work

_spitfire_projs() {
    candidate="${COMP_WORDS[-1]}"
    COMPREPLY=($(compgen -W "$(ls $WORK | grep 'Spitfire' | sed 's/Spitfire//')" "$candidate"))
}

# usage: `spitfire-debug CoreServices` or `spitfire-debug StrepplusHAL` etc.
sdbg() {
	# if there's a bose subdir in the CWD (e.g. in the HAL) go there first
	[[ -d "$(pwd)"/bose ]] && pushd "bose"
    args=("${@/#/"$WORK/Spitfire"}")

    # the above only works for when we're running this command in a project that
    # has its conanfile in a nonstandard location. if we want to add such a
    # project as a dependency, however, we want to make sure that we're can use
    # the right directory
    for (( i=0; i<${#args[@]}; i++ )); do
        # if there's no conanfile in the top-level directory, find it
        if [[ ! -f "${args[$i]}"/conanfile.py ]]; then
            echo -e -n "\e[0;36mNo conanfile found in top-level directory ${args[$i]}, searching for one...\e[0m"
            conanfiles=("$(find "${args[$i]}" -name 'conanfile.py')")
            if [[ ${#conanfiles[@]} = 0 ]]; then
                echo "\\n\e[0;31mNo conanfile found in ${args[$i]}, skipping...\e[0m"
                args[$i]=""
                continue
            elif [[ ${#conanfiles[@]} > 1 ]]; then
                # this should never ever happen. lol
                echo "\\n\e[0;33mMultiple conanfiles found in ${args[$i]}, please select an option:\e[0m"
                select f in "${conanfiles[@]}"; do
                    echo "Using $f..."
                    if [[ ${f:+set} ]]; then
                        args[$i]="$(dirname "$f")"
                        break
                    fi
                done
            else
                # this is the typical case, so we can just continue silently
                args[$i]="$(dirname "${conanfiles[0]}")"
                echo -e "\e[0;32mFound! (\e[0;36m${args[$i]}\e[0;32m)\e[0m"
            fi
        else
            echo -e "\e[0;36mFound conanfile in top-level directory ${args[$i]}\e[0m"
        fi
    done

	spitfire debug -i --new "${args[@]}"

	# pop the directory stack back to where it was if we pushed bose to it
	# earlier
	popd &> /dev/null
}

scd() {
    cd $WORK/Spitfire$1
}

complete -F _spitfire_projs sdbg
complete -F _spitfire_projs scd

alias spexe="cmd.exe /c spitfire"
alias spls="spexe list-ports"

supd() {
    fw=$(find . -iname 'flash_image.xuv')
    if [[ ! -f $fw ]]; then
        printf "No firmware image found. Did you build?" >&2
        return 255
    fi
    spexe update "${@}" "$(wslpath -w $fw)"
}

# concatenate tests_debug.log.$n files under the CWD into a single file
catlogs() {
    find "${1:-.}" -name 'tests_debug.log*' -printf '%Ts %p\n' | sort -n | cut -d ' ' -f2- | xargs cat > "${2:-.}"/tests_debug.log
}


