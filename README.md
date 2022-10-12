# Home Assistant ENTSO-e Transparency Platform Energy Prices [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=J6LK5FLATEUNC)
Custom component for Home Assistant to fetch energy prices of all European countries from the ENTSO-e Transparency Platform (https://transparency.entsoe.eu/).
Day ahead energy prices are added as a sensor and can be used in automations to switch equipment. A 24 Hour forecast of the energy prices is in the sensors attributes.

#### API Access
You need an ENTSO-e Restful API key for this integration. To request this API key, register on the [Transparency Platform](https://transparency.entsoe.eu/) and send an email to transparency@entsoe.eu with “Restful API access” in the subject line.

### Sensors
The integration adds the following sensors:
- Average Day-Ahead Electricity Price Today
- Highest Day-Ahead Electricity Price Today
- Lowest Day-Ahead Electricity Price Today
- Current Day-Ahead Electricity Price
- Current Percentage Relative To Highest Electricity Price Of The Day
- Next Hour Day-Ahead Electricity Price
- Time Of Highest Energy Price Today
- Time Of Lowest Energy Price Today

------
## Installation

### Manual
Download this repository and place the contents of `custom_components` in your own `custom_components` map of your Home Assistant installation. Restart Home Assistant and add the integration through your settings. 

### HACS

Add https://github.com/JaccoR/hass-entso-e to your HACS custom repositories and install through HACS. Restart Home Assistant and add the integration through your settings. 

------
## Configuration

The sensors can be added using the web UI. In the web UI you can add your API-key and country and the sensors will automatically be added to your system. There is an optional field for an additional cost template.

### Additional Cost Template

In the optional field `Additional Cost Template` a template for additional costs, like hourly fixed costs, can be added. When left empty, no additional costs are added.
In this template `now()` always refers start of the hour of that price. this way we can calculate the correct costs and add that to the day ahead prices. 

An example template is given below:
```
{% set s = {
    "hourly_fixed_cost": 0.5352,
    "winter_night": 0.265,
    "winter_day": 0.465,
    "summer_day": 0.284,
    "summer_night": 0.246,
    "cert": 0.01
}
%}
{% if now().month >= 5 and now().month <11 %}
    {% if now().hour >=6 and now().hour <23 %}
        {{s.summer_day+s.hourly_fixed_cost+s.cert|float}}
    {% else %}
        {{s.summer_night+s.hourly_fixed_cost+s.cert|float}}
    {% endif %}
{% else %}
    {% if now().hour >=6 and now().hour <23 %}
        {{s.winter_day+s.hourly_fixed_cost+s.cert|float}}
    {%else%}
        {{s.winter_night+s.hourly_fixed_cost+s.cert|float}}
    {% endif %}
{% endif %}
```
------


#### Updates

The integration is in an early state and receives a lot of updates. If you already setup this integration and encounter an error after updating, please try redoing the above installation steps. 

------
## Integration

### Show prices graph with ApexCharts Card

You can show a nice graph with the prices by using the [ApexCharts Card](https://github.com/RomRider/apexcharts-card)

![Prices graph](images/PriceGraph.png)

Add the ApexCharts Card from HACS.

```yaml
type: custom:apexcharts-card
graph_span: 48h
update_delay: 2s
span:
  start: day
now:
  show: true
  label: Now
header:
  show: false
  title: Day ahead prices
  show_states: true
  colorize_states: true
series:
  - entity: sensor.current_electricity_market_price
    type: column
    name: Today
    float_precision: 4
    data_generator: |
      return entity.attributes.prices_today.map((data, index) => {
        return [data.time, data.price];
      });
  - entity: sensor.current_electricity_market_price
    name: Tomorrow
    type: column
    float_precision: 4
    data_generator: |
      return entity.attributes.prices_tomorrow.map((data, index) => {
        return [new Date(data.time).getTime(), data.price];
      });
```
