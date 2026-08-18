restart() {
    read -p "Type yes to restart: " confirm
    if [ "$confirm" = "yes" ]; then
        sudo systemctl reboot
    else
        echo "Cancelled."
    fi
}
