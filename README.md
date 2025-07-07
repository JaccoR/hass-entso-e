# Home Assistant ENTSO-e Transparency Platform Energy Prices [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=J6LK5FLATEUNC)
Custom component for Home Assistant to fetch energy prices of all European countries from the ENTSO-e Transparency Platform (https://transparency.entsoe.eu/).
Day ahead energy prices are added as a sensor and can be used in automations to switch equipment. A 24 Hour forecast of the energy prices is in the sensors attributes and can be shown in a graph:

<p align="center">
    <img src="https://user-images.githubusercontent.com/31140879/195382579-c87b3285-c599-4e30-867e-1acf9feffabe.png" width=40% height=40%>
</p>

### API Access
You need an ENTSO-e Restful API key for this integration. To request this API key, register on the [Transparency Platform](https://transparency.entsoe.eu/) and send an email to transparency@entsoe.eu with “Restful API access” in the subject line. Indicate the
email address you entered during registration in the email body.

### Sensors
The integration adds the following sensors:
- Average Day-Ahead Electricity Price Today (This integration carries attributes with all prices)
- Highest Day-Ahead Electricity Price Today
- Lowest Day-Ahead Electricity Price Today
- Current Day-Ahead Electricity Price
- Current Percentage Relative To Highest Electricity Price Of The Day
- Next Hour Day-Ahead Electricity Price
- Time Of Highest Energy Price Today
- Time Of Lowest Energy Price Today
  
------
## Installation

### HACS

Search for "ENTSO-e" when adding HACS integrations and add "ENTSO-e Transparency Platform". 

Or use this link to go directly there: [![Or use this link.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JaccoR&repository=hass-entso-e&category=integration) 

Restart Home Assistant and add the integration through Settings. 

### Manual
Download this repository and place the contents of `custom_components` in your own `custom_components` map of your Home Assistant installation. Restart Home Assistant and add the integration through your settings. 

------
## Configuration

The sensors can be added using the integration page.

#### Add integration

1. Go to Settings => Devices and Services
2. Click the button "+ Add integration". 
2. Search for "entso
3. Click on the Entso-e to start te configuration flow.

 In the config flow you can add your API-key and country and the sensors will automatically be added to your system. There is an optional field for a cost modifyer template and resulting currency.

### Cost Modifyer Template

In the optional field `Price Modifyer Template` a template to modify the price to add additional costs (such as fixed costs per kWh and VAT) and currency conversion (based on a currency sensor) can be specified. When left empty, no additional costs are added.
In this template `now()` always refers start of the hour of that price and `current_price` refers to the price itself. This way day ahead price can be modified to correct for extra costs.

An example template is given below. You can find and share other templates [here](https://github.com/JaccoR/hass-entso-e/discussions/categories/price-modifyer-templates).
```
{% set s = {
    "extra_cost": 0.5352,
    "winter_night": 0.265,
    "winter_day": 0.465,
    "summer_day": 0.284,
    "summer_night": 0.246,
    "VAT": 0.21
}
%}
{% if now().month >= 5 and now().month <11 %}
    {% if now().hour >=6 and now().hour <23 %}
        {{(current_price + s.summer_day+s.extra_cost) * s.VAT | float}}
    {% else %}
        {{(current_price + s.summer_night + s.extra_cost) * s.VAT | float}}
    {% endif %}
{% else %}
    {% if now().hour >=6 and now().hour <23 %}
        {{(current_price + s.winter_day + s.extra_cost) * s.VAT | float}}
    {%else%}
        {{(current_price + s.winter_night + s.extra_cost) * s.VAT | float}}
    {% endif %}
{% endif %}
```
### Calculation method
This changes the calculated (min,max,avg values) entities behaviour to one of:

- Sliding
The min/max/etc entities will get updated every hour with only upcoming data.
This means that the min price returned at 13:00 will be the lowest price in the future (as available from that point in time).
Regardless of past hours that might have had a lower price (this is most useful if you want to be able to schedule loads as soon and cheap as possible)

- Default (on publish)
The min/max/etc entities will get updated once new data becomes available.
This means that the min price will update once the next days pricing becomes available (usually between 12:00 and 15:00)
It also means that until the next days pricing becomes available the latest 48h of available data will be used to calculate a min price

- Rotation
The min/max/etc entities will get updated at midnight.
This means that the min price returned at 23:59 will  be based on the day x price while at 00:00 the day x+1 price will be the only one used in the calculations)
day x in this case is a random date like 2022-10-10 and day x+1 2022-10-11


### ApexChart Graph
Prices can be shown using the [ApexChart Graph Card](https://github.com/RomRider/apexcharts-card) like in the example above. The Lovelace code for this graph is given below:

```
type: custom:apexcharts-card
graph_span: 24h
span:
  start: day
now:
  show: true
  label: Now
header:
  show: true
  title: Electriciteitsprijzen Vandaag (€/kwh)
yaxis:
  - decimals: 2
series:
  # This is the entity ID with no name configured.
  # When a name is configured it will be sensor.<name>_average_electricity_price.
  - entity: sensor.average_electricity_price
    stroke_width: 2
    float_precision: 3
    type: column
    opacity: 1
    color: ''
    data_generator: |
      return entity.attributes.prices.map((entry) => { 
      return [new Date(entry.time), entry.price];
      });

```


------

#### Updates

The integration is in an early state and receives a lot of updates. If you already setup this integration and encounter an error after updating, please try redoing the above installation steps. 

