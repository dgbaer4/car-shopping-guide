# Car Shopping Guide

Car Shopping Guide is an independent vehicle-shopping interview and recommendation tool. The **v0.3 Pilot Preview** helps shoppers compare vehicles for an outright cash purchase.

[Open the Pilot Preview](https://dgbaer4.github.io/car-shopping-guide/) · [Changelog](CHANGELOG.md)

## Using the pilot

Answer the interview questions, review your buyer profile, and open the recommendations. The results summarize confirmed and possible matches and link to each vehicle's details. Use the financial assumptions and vehicle price overrides to compare purchase and ownership costs. Interview progress stays in your browser, and you can export a copy of your buyer profile.

The pilot uses a limited U.S. vehicle catalog. Sourced asking prices and MSRP are reference estimates. Verify the exact vehicle, equipment, and seller quote before buying. Safety ratings and live inventory are outside the pilot scope.

## Development and releases

Use `staging` for acceptance testing and `main` for approved release packages. To serve an approved package locally, run `python -m http.server 8000` from the repository root and open `http://localhost:8000/`. Keep personal buyer responses out of this public repository.

The v0.3 package was accepted on a physical iPad in Safari. [Staging acceptance record](https://github.com/dgbaer4/car-shopping-guide/issues/11#issuecomment-7181409833)
