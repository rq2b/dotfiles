# dotfiles

## how to apply
```bash
git clone https://github.com/rq2b/dotfiles ~/dotfiles
cd ~/dotfiles
stow -d stow -t ~ *
```

## how to update
```bash
cd ~/dotfiles
git pull
stow -R -d stow -t ~ *
```

## how to double-check
```bash
stow -n -v -d stow -t ~ core
```
