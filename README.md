# Home Assistant ENSO-e Transparency Platform Prices
Integration for Home Assistant to fetch energy prices and information from the ENTSO-e Transparency Platform (https://transparency.entsoe.eu/).
Day ahead energy prices are added as a sensor and can be used in automations to switch equipment.
 
### Disclaimer
This integration is in a very early state and a work in progress. For now, only dutch energy prices can be fetched.

#### API Access
You need an ENTSO-e Restful API key for this integration. To request this API key, register on the [Transparency Platform](https://transparency.entsoe.eu/) and send an email to transparency@entsoe.eu with “Restful API access” in the subject line. The ENTSO-e Helpdesk will make their best efforts to respond to your request within 3 working days.

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
