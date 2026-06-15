from gi.repository import Nautilus, GObject, Gio
import subprocess
import os


class FollowSymlinkExtension(GObject.GObject, Nautilus.MenuProvider):

    def get_file_items(self, files):
        if len(files) != 1:
            return []

        file = files[0]

        try:
            path = file.get_location().get_path()
        except Exception:
            return []

        if not path or not os.path.islink(path):
            return []

        item = Nautilus.MenuItem(
            name="FollowSymlink",
            label="Follow Symlink",
            tip="Open the symlink target"
        )

        item.connect("activate", self.follow_symlink, path)

        return [item]

    def follow_symlink(self, menu, path):
        target = os.path.realpath(path)

        subprocess.Popen([
            "nautilus",
            target
        ])
