# Home Assistant ENSO-e Transparency Platform Prices
Integration for Home Assistant to fetch day ahead energy prices from the ENTSO-e Transparency Platform.
Energy prices are added as a sensor and can be used in automations to switch equipment.
 
### Disclaimer
This integration is in a very early state. For now, only dutch energy prices can be fetched.

### Sensors
The integration adds the following sensors:
- Average Electricity Price Today
- Highest Electricity Price Today
- Lowest Electricity Price Today
- Current Electricity Price

## Installation

### Manual
Download this repository and place the contents of "custom_components" in the custom_components map of your Home Assistant installation. Restart Home Assistant and add the integration through your settings and you're set!

### HACS
Add https://github.com/JaccoR/hass-entso-e to your HACS custom repositories and install through HACS. Restart Home Assistant and add the integration through your settings and you're set!
