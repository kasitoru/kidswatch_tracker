# Kids Watch Tracker for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](https://github.com/kasitoru/kidswatch_tracker/archive/refs/heads/main.zip)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2022.8%2B-orange)](https://www.home-assistant.io)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/kasitoru/kidswatch_tracker/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org)
[![Donate](https://img.shields.io/badge/donate-YooMoney-blueviolet.svg)](https://yoomoney.ru/to/4100110221014297)

Integration for tracking Kids Watch devices (such as HONOR Choice Kids Watch) in Home Assistant.

## Installation

### Method 1: Via HACS (Recommended)

1. Ensure you have [HACS](https://hacs.xyz) installed
2. In HACS, go to "Integrations"
3. Click the three dots in the top right → "Custom repositories"
4. Add the repository URL: `https://github.com/kasitoru/kidswatch_tracker`
5. Select category "Integration"
6. Search for "Kids Watch Tracker" in HACS and install it
7. Restart Home Assistant

### Method 2: Manual Installation

1. Download the [archive](https://github.com/kasitoru/kidswatch_tracker/archive/refs/heads/main.zip) with the latest version of the integration
2. Copy the `kidswatch_tracker` folder to your `custom_components` directory
3. Restart Home Assistant

## Configuration

### UI Configuration

1. After installation, go to Settings → Devices & Services → Integrations
2. Click "Add Integration"
3. Search for "Kids Watch Tracker"
4. Fill in the configuration form:
   - **Country Code**: Select your country from the dropdown list
   - **Phone Number**: Phone number associated with your Kids Watch account
   - **Password**: Password for your Kids Watch account
   - **Update Interval**: How often to update location (seconds, default: 60)
   - **Force Update Location**: If enabled, will request location update on every poll

### Configuration Options

After setup, you can adjust settings via the integration's "Configure" menu:

- **Update Interval**: 30 to 3600 seconds
- **Force Update Location**: Enable/disable

## Entities

For each child/device, the following entities are created:

### Device Tracker
- `device_tracker.kidswatch_tracker_[device_id]`: Main location tracking entity

### Attributes:
- **locate_time**: Last location update timestamp
- **charging**: Whether device is charging (true/false)
