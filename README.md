# dotfiles

## how to apply

```bash
git clone https://github.com/rq2b/dotfiles ~/dotfiles  
cd ~/dotfiles  
stow --no-folding -d stow -t ~ *
```

---

## how to update
```bash
cd ~/dotfiles  
git pull  
stow --no-folding -R -d stow -t ~ *
```

---

## how to double-check
```bash
stow --no-folding -n -v -d stow -t ~ *
```

