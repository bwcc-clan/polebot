# Polebot

The Polebot is a bot that works with the awesome [HLL CRCON Tool](https://github.com/MarechJ/hll_rcon_tool) to enable
admins to manage their server better.

## Features

Features include:

### Votemap improver

This works alongside the existing mechanism to enable greater control of the maps that are selected for votemap. As this
capability is not exposed by default, we have to use a slightly devious mechanism to achieve it:

1. Wait for a MAP_START message.
2. Calculate our own map selection. This is based on the same settings as the standard votemap configuration, but it
   features an improved algorithm that enables closer control of the maps that are suggested.
3. Call `api/get_votemap_whitelist` to retrieve the configured whitelist and save it.
4. Call `api/set_votemap_whitelist` to set the whitelist to just the maps that we have selected.
5. Call `api/reset_votemap_state` to force CRCON to regenerate the votemap options. Since there are only the options
   that we have calculated, these should therefore be the options that are offered.
6. Call `api/set_votemap_whitelist` to restore the whitelist to its original value.

Note that there is a risk of difficulty if step 6 fails to run for some reason. If this occurs, the best thing is to
manually reset the whitelist through the CRCON UI.

### Send player messages

Send messages to players in-game.

### Show VIP

Individual Discord server members can display their own VIP status.

## User account setup

To allow Polebot to connect to your CRCON server, you must set up a user with the following permissions, then create an
API key that you will use when configuring the server connection in Discord.

```text
admin | log entry | Can view log entry
api | rcon user | Can add a map to the votemap whitelist
api | rcon user | Can add maps to the rotation
api | rcon user | Can add multiple maps to the votemap whitelist
api | rcon user | Can add VIP status to players
api | rcon user | Can change the Log Stream config
api | rcon user | Can change the votemap settings
api | rcon user | Can download the VIP list
api | rcon user | Can message players
api | rcon user | Can remove all VIPs
api | rcon user | Can remove a map from the votemap whitelist
api | rcon user | Can remove maps from the rotation
api | rcon user | Can remove multiple maps from the votemap whitelist
api | rcon user | Can remove VIP status from players
api | rcon user | Can reset the votemap whitelist
api | rcon user | Can reset votemap selection & votes
api | rcon user | Can set the votemap whitelist
api | rcon user | Can upload a VIP list
api | rcon user | Can view all possible maps
api | rcon user | Can view the current gamestate
api | rcon user | Can view get_players endpoint (name, steam ID, VIP status and sessions) for all connected players
api | rcon user | Can view the get_status endpoint (server name, current map, player count)
api | rcon user | Can view the Log Stream config
api | rcon user | Can view the votemap whitelist
api | rcon user | Can view the player name of all connected players with a HLL game server admin role
api | rcon user | Can view the get_player_info endpoint (Name, steam ID, country and steam bans)
api | rcon user | Can view messages sent to players
api | rcon user | View the detailed player profile page
api | rcon user | Can view the current/max players on the server
api | rcon user | Can view the get_playerids endpoint (name and steam IDs of connected players)
api | rcon user | Can view recent logs (Live view)
api | rcon user | Can view the get_structured_logs endpoint
api | rcon user | Can view the number of connected VIPs
api | rcon user | Can view all players with VIP and their expiration timestamps
api | rcon user | Can view the votemap settings
api | rcon user | Can view the current votemap status (votes, results, etc)
```

## Credits / Attributions

[Polecat icons created by Freepik - Flaticon]([https://www.flaticon.com/free-icons/polecat "polecat icons")
