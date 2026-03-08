# dotfiles

## Clone

```bash
git clone https://github.com/rq2b/dotfiles ~/dotfiles
cd ~/dotfiles
````

---

## Apply dotfiles

### Apply one package

```bash
cd ~/dotfiles/stow
stow --no-folding -t ~ core
```

### Apply all packages

```bash
cd ~/dotfiles/stow
stow --no-folding -t ~ *
```

---

## Update

```bash
cd ~/dotfiles
git pull

cd ~/dotfiles/stow
stow --no-folding -R -t ~ *
```

---

## Dry-run / verify

### Check one package

```bash
cd ~/dotfiles/stow
stow --no-folding -n -v -t ~ core
```

### Check all packages

```bash
cd ~/dotfiles/stow
stow --no-folding -n -v -t ~ *
```

---

## Alternative: run from repo root

```bash
cd ~/dotfiles
stow --no-folding -d stow -t ~ core
```

Do not use `*` from the repository root, because it expands to non-package files/directories there.
