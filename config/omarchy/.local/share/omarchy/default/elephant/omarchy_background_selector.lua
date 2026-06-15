Name = "omarchyBackgroundSelector"
NamePretty = "Omarchy Background Selector"
Cache = false
HideFromProviderlist = true
SearchName = true

local function ShellEscape(s)
  return "'" .. s:gsub("'", "'\\''") .. "'"
end

function FormatName(filename)
  -- Remove leading number and dash
  local name = filename:gsub("^%d+", ""):gsub("^%-", "")
  -- Remove extension
  name = name:gsub("%.[^%.]+$", "")
  -- Replace dashes with spaces
  name = name:gsub("-", " ")
  -- Capitalize each word
  name = name:gsub("%S+", function(word)
    return word:sub(1, 1):upper() .. word:sub(2):lower()
  end)
  return name
end

-- helper: run command safely
local function read_cmd(cmd)
  local handle = io.popen(cmd)
  if not handle then return nil end
  local result = handle:read("*l")
  handle:close()
  return result
end

-- detect active monitor
local function get_active_monitor()
  return read_cmd(
    "hyprctl monitors -j | jq -r '.[] | select(.focused==true).name'"
  )
end

-- map monitor → mode
local function get_mode(monitor)
  if monitor == "DP-1" then
    return "horizontal"
  elseif monitor == "HDMI-A-1" then
    return "vertical"
  else
    return "horizontal" -- safe fallback
  end
end

local function get_aspect_mode(file)
  local filename = file:match("([^/]+)$")
  if not filename then return nil end

  filename = filename:lower()

  if filename:find("horizontal") then
    return "horizontal"
  elseif filename:find("vertical") then
    return "vertical"
  end

  return nil
end

function GetEntries()
  local entries = {}
  local home = os.getenv("HOME")

  -- Read current theme name
  local theme_name_file = io.open(home .. "/.config/omarchy/current/theme.name", "r")
  local theme_name = theme_name_file and theme_name_file:read("*l") or nil
  if theme_name_file then
    theme_name_file:close()
  end

  -- determine active monitor + mode
  local active_monitor = get_active_monitor()
  local mode = get_mode(active_monitor)

  -- Directories to search
  local dirs = {
    home .. "/.config/omarchy/current/theme/backgrounds",
  }
  if theme_name then
    table.insert(dirs, home .. "/.config/omarchy/backgrounds/" .. theme_name)
  end

  -- Track added files to avoid duplicates
  local seen = {}

  for _, wallpaper_dir in ipairs(dirs) do
    local handle = io.popen(
      "find " .. ShellEscape(wallpaper_dir)
      .. " -maxdepth 1 \\( -type f -o -type l \\) \\( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' -o -name '*.gif' -o -name '*.bmp' -o -name '*.webp' \\) 2>/dev/null | sort"
    )
    if handle then
      for background in handle:lines() do
        local filename = background:match("([^/]+)$")
        if filename and not seen[filename] then
          local aspect = get_aspect_mode(background)

          -- SAFE filter: allow if matches OR detection failed
          if aspect == nil or aspect == mode then
            seen[filename] = true

            table.insert(entries, {
            Text = FormatName(filename),
            Value = background,
            Actions = {
              activate = "omarchy-theme-bg-set " .. ShellEscape(background),
            },
            Preview = background,
            PreviewType = "file",
          })
          end
        end
      end
      handle:close()
    end
  end

  return entries
end
