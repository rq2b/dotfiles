stop_syncthing() {
    if systemctl --user is-active --quiet syncthing.service; then
        systemctl --user stop syncthing.service || \
            die "Restore hook failed for dataset '$1': could not stop syncthing.service."
    fi
}