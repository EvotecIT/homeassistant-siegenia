# Automations and dashboards

[Back to the README](../README.md) · [Configuration](configuration.md)

## Add a dashboard

Use the controller's `cover` entity with a standard Home Assistant Tile card.
The repository includes a [basic tile example](../examples/lovelace/tile-basic.yaml)
and optional Mushroom [compact](../examples/lovelace/mushroom-compact.yaml) and
[detailed](../examples/lovelace/mushroom-detailed.yaml) examples.
Mushroom examples require that custom card to be installed separately.

Replace example entity IDs with your own. Displayed percentages represent
controller modes, not measured opening distances.

## Test a mode deliberately

In **Developer tools → Actions**, select **Siegenia: Set Window Mode** and choose
your cover. For example, this requests gap ventilation:

```yaml
action: siegenia.set_mode
target:
  entity_id: cover.my_window
data:
  mode: GAP_VENT
```

`cover.my_window` is a placeholder. The available command names are `OPEN`,
`CLOSE`, `GAP_VENT`, `CLOSE_WO_LOCK`, `STOP_OVER`, and `STOP`; the controller
must support the requested mode.

This can move the window. Keep the opening clear and supervise the first test.
Do not infer a safe operating state solely from an automation trigger.

## Timers

The integration exposes `siegenia.timer_start`, `siegenia.timer_stop`, and
`siegenia.timer_set_duration`. Duration accepts nonnegative whole minutes or `HH:MM`, with a minute field
from `00` to `59`. Each integration action accepts one entity; use a repeat
action when applying the same command to several controllers.

Choose the target and inspect the controller's timer behavior before using it
unattended. A timer setting is not a substitute for checking whether a moving
window is safe.

## Example: synchronize the clock

This automation synchronizes the controller clock at 03:15 using Home Assistant's
local time. It does not send an open or close command.

```yaml
alias: Siegenia nightly clock sync
triggers:
  - trigger: time
    at: "03:15:00"
conditions:
  - condition: template
    value_template: "{{ states('cover.my_window') not in ['unavailable', 'unknown'] }}"
actions:
  - action: siegenia.sync_clock
    target:
      entity_id: cover.my_window
mode: single
```

For installations needing an explicit timezone string, the action accepts an
optional `timezone` field in POSIX/TZ format. Leave it out unless required.

## Maintenance actions

Reboot, factory reset, and certificate renewal are separate maintenance actions.
Do not place them in routine reconnect or retry automations. Diagnose a
connection problem with [the support guide](SUPPORT.md) first.


## Repair registry names

The `siegenia.repair_names` action previews proposed repairs by default and
reports them in a persistent notification. Review that report before setting
`dry_run: false`. Entity IDs stay unchanged unless `rename_entity_ids: true`;
renaming an ID can require updating automations that reference it.

The `siegenia.cleanup_devices` action merges duplicate registry devices for one
integration entry. Set `entity_id` to a Siegenia entity to choose the entry
explicitly; invalid or unrelated targets are rejected.
