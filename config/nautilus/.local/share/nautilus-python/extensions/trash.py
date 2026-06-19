from gi.repository import Nautilus, GObject

import subprocess
import shlex


class TrashExtension(GObject.GObject, Nautilus.MenuProvider):
    def get_file_items(self, files):

        if not files:
            return []

        stage_item = Nautilus.MenuItem(
            name="TrashStage",
            label="Copy trash remove command",
            tip="Copy a trash remove command to the clipboard",
        )

        stage_item.connect(
            "activate",
            self.copy_remove_command,
            files,
        )

        delete_item = Nautilus.MenuItem(
            name="TrashDelete",
            label="Copy trash delete command",
            tip="Copy a trash delete command to the clipboard",
        )

        delete_item.connect(
            "activate",
            self.copy_delete_command,
            files,
        )

        return [
            stage_item,
            delete_item,
        ]

    def get_paths(self, files):

        paths = []

        for file_obj in files:

            try:
                location = file_obj.get_location()

                if location is None:
                    continue

                path = location.get_path()

                if path is None:
                    continue

                paths.append(path)

            except Exception:
                continue

        return paths

    def build_command(
        self,
        base_args,
        paths,
    ):

        args = list(base_args)

        args.extend(paths)

        return " ".join(shlex.quote(arg) for arg in args)

    def copy_to_clipboard(self, text):

        try:

            subprocess.run(
                ["wl-copy"],
                input=text,
                text=True,
                check=True,
            )

            return

        except Exception:
            pass

        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            check=True,
        )

    def notify(self, text):

        try:

            subprocess.run(
                [
                    "notify-send",
                    "Trash",
                    text,
                ],
                check=False,
            )

        except Exception:
            pass

    def copy_remove_command(
        self,
        menu,
        files,
    ):

        paths = self.get_paths(files)

        command = self.build_command(
            [
                "trash",
                "remove",
            ],
            paths,
        )

        self.copy_to_clipboard(command)

        self.notify("trash remove command copied")

    def copy_delete_command(
        self,
        menu,
        files,
    ):

        paths = self.get_paths(files)

        command = self.build_command(
            [
                "trash",
                "delete",
                "--confirm",
            ],
            paths,
        )

        self.copy_to_clipboard(command)

        self.notify("trash delete command copied")
