-- HD2-Addon: mods/bass/keep_walking
-- Optional Bingus companion for Keep Walking.
-- Registers hotkeys on Options > Keyboard and Mouse > Change Bindings > Mods
-- and writes them as actions for KeepWalking.exe. The exe still owns the
-- virtual stick; this addon only steers the hotkeys while it is loaded.

if rawget(_G, 'BassKeepWalking') then return end

local CATEGORY = 'Keep Walking'
-- Chat is not a mod bind. Keep Walking reads the game's own Open Chat key.
local BINDS = {
    { id = 'bass.keep_walking.walk', label = 'Walk / Run', key = 'walk' },
    { id = 'bass.keep_walking.speed_up', label = 'Faster', key = 'up' },
    { id = 'bass.keep_walking.speed_down', label = 'Slower', key = 'down' },
}

local loader = rawget(_G, 'CowboyBingusModLoader')
local log_file
if loader and type(loader.open_log) == 'function' then
    pcall(function() log_file = loader.open_log('KeepWalking.log') end)
end

local function note(message)
    if log_file then
        pcall(function()
            log_file:write(message .. '\n')
            log_file:flush()
        end)
    end
end

local function dir_path()
    local base = os.getenv('LOCALAPPDATA')
    if not base or base == '' then return nil end
    return base .. '\\CowboyBingus\\Helldivers2'
end

local function mod_path()
    local directory = dir_path()
    if not directory then return nil end
    return directory .. '\\KeepWalking.mod'
end

local state = {
    registered = false,
    clock = 0,
    next_write = 0,
    held = {},
    count = { walk = 0, up = 0, down = 0 },
}

for _, bind in ipairs(BINDS) do
    state.held[bind.key] = false
end

local function write_mod()
    local path = mod_path()
    if not path then return end
    local file = io.open(path, 'w')
    if not file then
        note('Could not write ' .. path)
        return
    end
    file:write(string.format(
        'alive=1\nt=%.3f\nwalk_n=%d\nup_n=%d\ndown_n=%d\n',
        state.clock,
        state.count.walk,
        state.count.up,
        state.count.down
    ))
    file:close()
end

local function ensure_bindings()
    local menu = rawget(_G, 'ModBindingsMenu')
    if not menu or menu.api ~= 1 then return menu end
    if type(menu.version) == 'number' and menu.version < 2 then
        note('Mod Bindings Menu v2+ required for Keep Walking.')
        return menu
    end
    if state.registered then return menu end
    local ok_all = true
    for _, bind in ipairs(BINDS) do
        local ok, err = menu.register_binding(bind.id, bind.label, nil, {
            category = CATEGORY,
        })
        if not ok then
            ok_all = false
            if err then note('Binding ' .. bind.id .. ' failed: ' .. tostring(err)) end
        end
    end
    if ok_all then
        state.registered = true
        note('Registered Keep Walking binds on the MODS tab.')
        write_mod()
    end
    return menu
end

local function step(dt)
    state.clock = state.clock + (tonumber(dt) or 0)
    local menu = ensure_bindings()
    if menu and state.registered then
        for _, bind in ipairs(BINDS) do
            local down = menu.is_down(bind.id)
            if down ~= nil then
                if down and not state.held[bind.key] then
                    state.count[bind.key] = state.count[bind.key] + 1
                    write_mod()
                    note('pulse ' .. bind.key .. ' n=' .. state.count[bind.key])
                end
                state.held[bind.key] = down and true or false
            end
        end
    end
    if state.clock >= state.next_write then
        state.next_write = state.clock + 0.25
        if state.registered then write_mod() end
    end
end

local previous_update = rawget(_G, 'update')
update = function(dt)
    local ok, err = pcall(step, dt)
    if not ok then note('Update error: ' .. tostring(err)) end
    if type(previous_update) == 'function' then return previous_update(dt) end
end

_G.BassKeepWalking = { api = 1 }
note('Keep Walking addon loaded. Bind keys on Options > MODS > Keep Walking.')
