-- HD2-Addon: mods/bass/walk_toggle
-- Bingus side of walk toggle. The MODS binding flips walk mode and this addon
-- starts the local companion, which holds the virtual stick at walk magnitude.
-- The companion is required: the game Lua VM cannot create a gamepad.

if rawget(_G, 'BassWalkToggle') then return end

local ffi = require('ffi')

ffi.cdef[[
typedef unsigned short WT_u16;
typedef unsigned int WT_u32;
typedef unsigned long long WT_u64;
void *OpenProcess(WT_u32 access, int inherit, WT_u32 pid);
int CloseHandle(void *handle);
void *ShellExecuteW(void *hwnd, const WT_u16 *op, const WT_u16 *file,
                    const WT_u16 *params, const WT_u16 *dir, int show);
]]

local kernel32 = ffi.load('kernel32')
local shell32 = ffi.load('shell32')

local BINDING_ID = 'bass.walk_toggle.toggle'
local MAG = 0.85
local PYTHON = [[C:\Users\bassa\AppData\Local\Python\pythoncore-3.14-64\pythonw.exe]]
local SCRIPT = [[O:\Helldivers 2 mods\walk-toggle\companion\walk_toggle.py]]

local loader = rawget(_G, 'CowboyBingusModLoader')
local log_file
if loader and type(loader.open_log) == 'function' then
    pcall(function() log_file = loader.open_log('WalkToggle.log') end)
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

local function state_path()
    local directory = dir_path()
    if not directory then return nil end
    return directory .. '\\WalkToggle.state'
end

local function pid_path()
    local directory = dir_path()
    if not directory then return nil end
    return directory .. '\\WalkToggle.companion.pid'
end

local state = {
    walk = false,
    was_down = false,
    registered = false,
    next_launch = 0,
    clock = 0,
}

local function widen(text)
    local buf = ffi.new('WT_u16[?]', #text + 1)
    for index = 1, #text do
        buf[index - 1] = text:byte(index)
    end
    buf[#text] = 0
    return buf
end

local function write_state()
    local path = state_path()
    if not path then return end
    local file = io.open(path, 'w')
    if not file then
        note('Could not write ' .. path)
        return
    end
    file:write(string.format('walk=%d\nmag=%.2f\n', state.walk and 1 or 0, MAG))
    file:close()
end

local function process_alive(pid)
    if not pid or pid <= 0 then return false end
    local handle = kernel32.OpenProcess(0x1000, 0, pid)
    if handle == nil or handle == ffi.NULL then return false end
    kernel32.CloseHandle(handle)
    return true
end

local function companion_alive()
    local path = pid_path()
    if not path then return false end
    local file = io.open(path, 'r')
    if not file then return false end
    local pid = tonumber(file:read('*a') or '')
    file:close()
    return process_alive(pid)
end

local function launch_companion()
    if companion_alive() then return end
    local op = widen('open')
    local file = widen(PYTHON)
    local params = widen('"' .. SCRIPT .. '"')
    local code = tonumber(ffi.cast('WT_u64', shell32.ShellExecuteW(nil, op, file, params, nil, 0))) or 0
    if code <= 32 then
        note('Companion launch failed, ShellExecute code ' .. code)
    else
        note('Companion launch requested.')
    end
end

local function set_walk(enabled)
    if state.walk == enabled then return end
    state.walk = enabled
    write_state()
    note(enabled and ('Walk ON (stick ' .. MAG .. ', companion).') or 'Walk OFF.')
end

local function ensure_binding()
    local menu = rawget(_G, 'ModBindingsMenu')
    if not menu or menu.api ~= 1 or state.registered then return menu end
    local ok, err = menu.register_binding(BINDING_ID, 'Toggle Walk', nil, {
        category = 'Walk Toggle',
    })
    if ok then
        state.registered = true
        note('Registered Toggle Walk. Set the key on Options > MODS > Walk Toggle.')
    elseif err then
        note('Binding registration failed: ' .. tostring(err))
    end
    return menu
end

local function step(dt)
    state.clock = state.clock + (tonumber(dt) or 0)
    local menu = ensure_binding()
    if state.clock >= state.next_launch then
        state.next_launch = state.clock + 3
        if not companion_alive() then launch_companion() end
    end
    if not menu or not state.registered then return end
    local down = menu.is_down(BINDING_ID)
    if down == nil then return end
    if down and not state.was_down then set_walk(not state.walk) end
    state.was_down = down and true or false
end

local previous_update = rawget(_G, 'update')
update = function(dt)
    local ok, err = pcall(step, dt)
    if not ok then note('Update error: ' .. tostring(err)) end
    if type(previous_update) == 'function' then return previous_update(dt) end
end

write_state()
_G.BassWalkToggle = {
    api = 1,
    walk = function() return state.walk end,
}
note('Walk Toggle loaded. Bind Toggle Walk on the MODS tab. Companion drives the stick at ' .. MAG .. '.')
