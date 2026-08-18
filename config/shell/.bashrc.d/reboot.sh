restart() {
    read -p "Type yes to restart: " confirm
    if [ "$confirm" = "yes" ]; then
        sudo systemctl reboot
    else
        echo "Cancelled."
    fi
}

reboot() {
    read -p "Type yes to reboot: " confirm
    [ "$confirm" = "yes" ] && sudo systemctl reboot || echo "Cancelled."
}
