## Purpose

Allows users to opt into viewing archived property listings (those marked `gone` during scraping) across the listings, map, and stats views.

## Requirements

### Requirement: Archived listings can be included in listing views

The system SHALL provide an opt-in option to include archived listings (status `gone`) in listing search, map, and statistics views. When the option is off, only active listings are shown, preserving current default behavior.

#### Scenario: Archived listings are hidden by default

- **WHEN** a client requests listings, map points, map hexes, or stats without the archived option
- **THEN** the response contains only listings with status `active`

#### Scenario: Archived listings are included when the option is set

- **WHEN** a client requests listings, map points, map hexes, or stats with the archived option enabled
- **THEN** the response contains listings with status `active` and `gone`, and archived listings remain identifiable by their `status` field

#### Scenario: Structured filters still apply to archived listings

- **WHEN** a client enables the archived option together with any combination of city, district, source, price, area, rooms, and market filters
- **THEN** the archived listings returned still satisfy all of the applied structured filters
