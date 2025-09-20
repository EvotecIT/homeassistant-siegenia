"""Embedded PNG brand assets.

These are simple, valid PNGs used to populate build/brand at startup.
Device/Integration tiles will actually use the SVG served by views,
but keeping PNGs on disk satisfies "proper" brand folder expectation.
"""

# 256x256 transparent pixel (placeholder if needed)
ICON_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAQAAAB1HAwCAAAACXBIWXMAAAsSAAALEgHS3X78AAAAB3RJTUUH5AgTFCk3N2p1lAAAAAlwSFlzAAAN1wAADdcBQiibeAAAABl0RVh0Q29tbWVudABDcmVhdGVkIHdpdGggR0lNUFeBDhcAAAAnSURBVHja7cExAQAAAMKg9U9tCF8gAAAAAAAAAAAAAAAAAAAAAPgBz+0AAaA2O1wAAAAASUVORK5CYII="
)

# 512x256 transparent pixel (placeholder)
LOGO_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAgAAAABACAQAAABb7j5iAAAACXBIWXMAAAsSAAALEgHS3X78AAAAB3RJTUUH5AgTFCk5Y6pQ7gAAABl0RVh0Q29tbWVudABDcmVhdGVkIHdpdGggR0lNUFeBDhcAAAAZSURBVHja7cExAQAAAMKg9U9tCF8gAAAAAAAAAAD4AcdwAAGU6p8gAAAAAElFTkSuQmCC"
)

