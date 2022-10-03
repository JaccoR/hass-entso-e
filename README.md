# Home Assistant ENTSO-e Transparency Platform Energy Prices
Custom component for Home Assistant to fetch energy prices and information of all European countries from the ENTSO-e Transparency Platform (https://transparency.entsoe.eu/).
Day ahead energy prices are added as a sensor and can be used in automations to switch equipment. 24 Hour forecast of the energy prices is in the sensors attributes.

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
- Time Of Highest Energy Price Today
- Time Of Lowest Energy Price Today

## Installation

### Manual
Download this repository and place the contents of `custom_components` in your own `custom_components` map of your Home Assistant installation. Restart Home Assistant and add the integration through your settings. Add your API-key and country and the sensors will automatically be added to your system.

### HACS

Add https://github.com/JaccoR/hass-entso-e to your HACS custom repositories and install through HACS. Restart Home Assistant and add the integration through your settings. Add your API-key and country and the sensors will automatically be added to your system.

#### Updates

The integration is in an early state and receives a lot of updates. If you already setup this integration and encounter an error after updating, please try redoing the above installation steps. 
