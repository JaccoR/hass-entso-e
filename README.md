# Home Assistant ENTSO-e Transparency Platform Energy Prices [![Donate](https://img.shields.io/badge/Donate-PayPal-green.svg)](https://www.paypal.com/donate/?hosted_button_id=J6LK5FLATEUNC)
Custom component for Home Assistant to fetch energy prices of all European countries from the ENTSO-e Transparency Platform (https://transparency.entsoe.eu/).
Day ahead energy prices are added as a sensor and can be used in automations to switch equipment. A 24 Hour forecast of the energy prices is in the sensors attributes and can be shown in a graph:

<p align="center">
    <img src="https://user-images.githubusercontent.com/31140879/195382579-c87b3285-c599-4e30-867e-1acf9feffabe.png" width=40% height=40%>
</p>

### API Access
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

Search for "ENTSO-e" when adding HACS integrations and add "ENTSO-e Transparency Platform". Restart Home Assistant and add the integration through your settings.

------
## Configuration

The sensors can be added using the web UI. In the web UI you can add your API-key and country and the sensors will automatically be added to your system. There is an optional field for an cost modifyer template.

### Cost Modifyer Template

In the optional field `Price Modifyer Template` a template to modify the price to add additional costs, such as fixed costs per kWh and VAT, can be added. When left empty, no additional costs are added.
In this template `now()` always refers start of the hour of that price and `current_price` refers to the price itself. This way day ahead price can be modified to correct for extra costs.

An example template is given below. You can find and share other templates [here](https://github.com/JaccoR/hass-entso-e/discussions/categories/price-modifyer-templates).
```
{% set s = {
    "extra_cost": 0.5352,
    "winter_night": 0.265,
    "winter_day": 0.465,
    "summer_day": 0.284,
    "summer_night": 0.246,
    "VAT": 1.21
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
series:
  # This is the entity ID with no name configured.
  # When a name is configured it will be sensor.<name>_average_electricity_price_today.
  - entity: sensor.average_electricity_price_today
    stroke_width: 2
    float_precision: 3
    type: column
    opacity: 1
    color: ''
    data_generator: |
      return entity.attributes.prices_today.map((record, index) => {
        return [record.time, record.price];
      });

```


------

### Getting prices for best priced windows
Sometimes it makes sense to find not only time for lowest price but also for a lengthy window where price
could be minimal. This might be useful for continuous loads like water heaters, dishwashers, car charging
stations or even room heaters if there is an intention to heat up a room during low prices and pause the
heating during high prices.

For that purpose the module contains 5 sensors named `time_of_lowest_price_window_for_X_hours_use`, where X can be 2, 3, 4 or 5.
Also there is a set of attributes with more detailed information about times and prices: `best_prices`  with time span from 1 to 5 hours and 30 minutes step. Each attribute entry includes length
of the window `window`, start time of the window `time`, total accumulated price `total`, average price
during the period `average` and average price outside of the period `average_other_time`.

The attributes can be used as templates in the automation:

 - check that time is within wanted window:

```
{# When a name is configured it will be sensor.<name>_time_of_lowest_price_window_for_5_hours_use #}
{% set ts = as_local(as_datetime(states.sensor.time_of_lowest_price_window_for_5_hours_use.state)) %}
{% set n = now() %}
{{ (n >= ts) and (n < (ts + timedelta(hours = 5))) }}
```
 - check the average price of the window:

```
{% set ns = namespace(index=-1) %}
{# When a name is configured it will be sensor.<name>_average_electricity_price_today #}
{% for price in states.sensor.average_electricity_price_today.attributes.best_prices %}
  {% if ns.index == -1 and price["window"] == 5.0 %}
    {% set ns.index = loop.index0 %}
  {% endif %}
{% endfor %}
{{ states.sensor.average_electricity_price_today.attributes.best_prices[ns.index]["average"] | float }}
```

### Example of automations based on the best/worst values

#### Water heater
The automation can be found in the `examples` folder. The `automation_water_heater.yaml` contains code for the following scenario:
 - automation restarts every 5 minutes
 - the automation assumes that on average the heating takes about 2.5 hours every day
 - also it is assumed that the heater has own relay that turn off heating after required temperature is reached
 - the automation switches off the heater control switch after some extra time to make sure the water is warm enough (5 hours selected)

#### Room heating
The automation can be found in the `examples` folder. The `automation_room_heater.yaml` contains code for the following scenario:
 - automation restarts every 5 minutes
 - automation defines 5 hours best prices window. It is assumed that heating up the room takes about 5 hours
 - when the heater is on, it should warm up the room to the 22 $^\circ$C during best prices
 - bad prices are defined by the comparing of the current price to the average of prices outside of the best window. The margin
   defines how high the current prices can be to become a "bad price"
 - if it is time of "bad price" then the heater is switched off but minimum temperature of 19 $^\circ$C is still guaranteed
 - otherwise average temperature of 21 $^\circ$C is kept outside of best hours


------


### Updates

The integration is in an early state and receives a lot of updates. If you already setup this integration and encounter an error after updating, please try redoing the above installation steps.

