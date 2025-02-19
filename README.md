# Polebot

The Polebot is a bot that works with the awesome [HLL CRCON Tool](https://github.com/MarechJ/hll_rcon_tool) to enable
admins to manage their server better.

Features include:

## Votemap improver

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

## Send player messages

Send messages to players in-game.

## Show VIP

Individual Discord server members can display their own VIP status.
