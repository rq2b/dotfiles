from gi.repository import Nautilus, GObject
import subprocess
from urllib.parse import unquote

class OpenKittyExtension(GObject.GObject, Nautilus.MenuProvider):

    def get_background_items(self, files):
        item = Nautilus.MenuItem(
            name="OpenKittyHere",
            label="Open Kitty Here",
            tip="Open Kitty in this directory"
        )

        def activate(menu, files):
            uri = files.get_location().get_uri()
            path = unquote(uri.replace("file://", ""))
            subprocess.Popen(["kitty", "--directory", path])

        item.connect("activate", activate, files)
        return [item]
