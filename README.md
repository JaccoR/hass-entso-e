# Home Assistant ENTSO-e Transparency Platform Energy Prices
Custom component for Home Assistant to fetch energy prices and information of all European countries from the ENTSO-e Transparency Platform (https://transparency.entsoe.eu/).
Day ahead energy prices are added as a sensor and can be used in automations to switch equipment.

This integration is in a very early state and a work in progress.

#### API Access
You need an ENTSO-e Restful API key for this integration. To request this API key, register on the [Transparency Platform](https://transparency.entsoe.eu/) and send an email to transparency@entsoe.eu with “Restful API access” in the subject line.

### Sensors
The integration adds the following sensors:
- Average Day-Ahead Electricity Price Today
- Highest Day-Ahead Electricity Price Today
- Lowest Day-Ahead Electricity Price Today
- Current Day-Ahead Electricity Price
- Current Percentage Of Highest Electricity Price Today
- Next Hour Day-Ahead Electricity Price

## Installation

### Manual
Download this repository and place the contents of `custom_components` in your own `custom_components` map of your Home Assistant installation. Restart Home Assistant and add the integration through your settings. Add your API-key and country and the sensors will automatically be added to your system.

### HACS

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/JaccoR/hass-entso-e)

Add https://github.com/JaccoR/hass-entso-e to your HACS custom repositories by clicking on the button above and install through HACS. Restart Home Assistant and add the integration through your settings. Add your API-key and country and the sensors will automatically be added to your system.
