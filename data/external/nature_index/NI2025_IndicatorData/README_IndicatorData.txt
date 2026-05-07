------------------
ABOUT
------------------

This document explains the contents of the following CSV files (and corresponding XLSX versions)
that are part of the indicator data package: 

- "Indikator_[id]_Dataset.csv" 
- "Indikator_[id]_DataRaw_Simulated.csv"
- "Indikator_[id]_DataScaled_Simulated.csv"
- "Indikator_[id]_Average.csv"

Note that the "[id]" will correspond to a single indicator's unique identifier if you have downloaded 
the dataset for only one indicator. If you have downloaded the entire dataset (all indicators), there
will be no "[id]_" in the file names.
The formats of the files are the same irrespective of whether all or just one indicator are contained. 

Together, the files are a compilation of different representations of indicator data used in the 2025 
update of the Norwegian Nature Index (NI): raw data as stored in the database ("Dataset"), raw data with 
simulated uncertainty summarized in a standardized way ("DataRaw_Simulated"), the same simulated data 
but standardized with respect to the reference values ("DataScaled_Simulated"), and area-weighted averages
calculated using the NI framework ("Average").

Below, you will find a detailed description of each of the four files, followed by instructions for citing 
the data. 

For more information and further reading, please visit https://www.naturindeks.no/ 
(in Norwegian with some additional references available in English). 
In addition, the workflow for generating the derivative data files ("DataRaw_Simulated", 
"DataScaled_Simulated", and "Average") from the raw data contained in the NI database ("Dataset")
is documented here: https://ninanor.github.io/NI-2025/indicator-data-calculations-and-visualizations.html
(All code is archived in the corresponding GitHub repository: https://github.com/NINAnor/NI-2025)


-----------------------------------------------
FILE DESCRIPTION - "Indikator_[id]_Dataset.csv"
-----------------------------------------------

This dataset contains the raw data exactly as it has been recorded by data providers in the NI database 
(https://naturindeks.nina.no/). It includes both observations for different area-year combinations and 
reference values for each area. Area delineations vary across different indicators.
Indicator observations are provided as means plus a measurement of uncertainty. 

For some indicators, uncertainty is provided as lower and upper quartile of an assumed uncertainty distrbution. 
For others, entire uncertainty distributions have been specified using the R package NIcalc. In the latter case, 
information on uncertainty is not included in the CSV file and needs to be accessed using NIcalc. Insturctions 
for this can be found in the workflow documentation:
https://ninanor.github.io/NI-2025/indicator-data-calculations-and-visualizations.html.

The CSV file contains only area-year combinations for which data has been recorded. Any missing area-year combinations
hence represent gaps/missing values in the database. 
 
************************
** Column definitions **
************************

AreaId = Integer identifier for area of indicator observations. Used primarily for internal linkages in the 
	database and hence not relevant for most other applications.

AreaName = Norwegian name of the area for which the indicator observation is relevant. Corresponding spatial
	extent/coverage can be found in the NI database or on the indicator's page on https://www.naturindeks.no/.
	The smallest spatial unit in use are municipalities; all areas are therefore either single municipalities
	or larger areas consisting of multiple municipalities. 

IndicatorId = Integer identifier for the indicator. Used primarily for internal linkages in the database and
	iterative operations in code. 
	
IndicatorName = Norwegian name of the indicator. Consistent with usage on https://www.naturindeks.no/.

YearId = Integer identifier for year of indicator observations. Used primarily for internal linkages in the 
	database and hence not relevant for most other applications. 

YearName = Year of indicator observation. "Reference" is used for the entries corresponding to reference values. 

Value = Average value of indicator observation.

Lower = Lower quartile of assumed uncertainty distribution of indicator observation. If missing/NA, uncertainty
	has been recorded using a custom distribution. To access information on the custom distribution, you have to 
	access the data using the R package NIcalc. 

Upper = Upper quartile of assumed uncertainty distribution of indicator observation. If missing/NA, uncertainty
	has been recorded using a custom distribution. To access information on the custom distribution, you have to 
	access the data using the R package NIcalc. 

DataTypeId = Integer code for the origin (type) of raw data. 1 = expert judgement, 2 = derived direcly from
	monitoring data, 3 = modelled estimate (typically based on monitoring data too). 

UnitOfMeasurement = The unit of values (columns "Value", "Lower, "Upper") as reported by the raw data provider.



------------------------------------------------------------------------------------------------------
FILE DESCRIPTIONS - "Indikator_[id]_DataRaw_Simulated.csv" & "Indikator_[id]_DataScaled_Simulated.csv"
------------------------------------------------------------------------------------------------------

Since the way uncertainty is reported for different indicators is heterogeneous, the NI framework internally fits
uncertainty distributions to all indicator observations and simulated from these distributions for all downstream
analyses and presentations. 

The files "Indikator_[id]_DataRaw_Simulated.csv" and "Indikator_[id]_DataScaled_Simulated.csv" contain statistical
summaries of 1000 bootstrap simulations from distributions of each indicator observation. The difference between the
two files is that the former contains data on the original scale (variable across indicators) while the latter consists
of "scaled" data values, i.e. values on a standardized scale from 0 (indicator absent/disappeared/extinct) to 1
(indicator at levels expected in intact nature). Values are transformed from the raw to the standardized scale by 
"scaling" relative to the a priori set reference values (not contained in this data, but present in 
"Indikator_[id]_Dataset.csv"). Notably, the scaled dataset does contain values > 1; this is because this dataset has not
been truncated yet. For the presentation of indicators on https://www.naturindeks.no/ and for using the indicators for
calculating area-weighted indicator averages and NI for ecosystems, the values are truncated such that any value > 1 
is set to 1.  

Aside from the distinction between raw and scaled indicator observations, the columns in the two files are identical.


************************
** Column definitions **
************************

id = Integer identifier for the indicator. Used primarily for internal linkages in the database and
	iterative operations in code. 

name = Norwegian name of the indicator. Consistent with usage on https://www.naturindeks.no/.

ICunitId = Integer identifier for area of indicator observations. Used primarily for internal linkages in the 
	database and NI calculations and hence not relevant for most other applications.

ICunitName = Norwegian name of the area for which the indicator observation is relevant. Corresponding spatial
	extent/coverage can be found in the NI database or on the indicator's page on https://www.naturindeks.no/.
	The smallest spatial unit in use are municipalities; all areas are therefore either single municipalities
	or larger areas consisting of multiple municipalities.

year = calendar year to which the indicator observation pertains. 

mean = arithmethic mean of the distribution of simulated indicator values. 

median = median (= 50% quantile) of the distribution of simulated indicator values.

sd = standard deviation of the distribution of simulated indicator values.

rel_sd = relative standard deviation (= sd/mean) of the distribution of simulated indicator values.

q025 = 2.5% quantile of the distribution of simulated indicator values. Corresponds to lower bound of 95% confidence interval. 

q05 = 5% quantile of the distribution of simulated indicator values.

q25 = 25% quantile (= lower quartile) of the distribution of simulated indicator values.

q75 = 75% quantile (= upper quartile) of the distribution of simulated indicator values.

q95 = 90% quantile of the distribution of simulated indicator values.

q975 = 97.5 % quantile of the distribution of simulated indicator values. Corresponds to upper bound of 95% confidence interval. 



-----------------------------------------------
FILE DESCRIPTION - "Indikator_[id]_Average.csv"
-----------------------------------------------

The three previous files contain indicator data at the original spatial scale, which is different across indicators. 
Using the NI calculation framework, it is possible to calculate area-weighed averages for each indicator and year. 
The area weights used for calculating these averages are based on how much of the area of each indicator observation
is covered by the ecosystems for which the indicator is relevant. The resulting "indicator indices" are on the same
scale as calculated NI values where 0 represents the indicator's condition in a completely destroyed ecosystem and 
1 represents the indicator's condition in an intact ecosystem. 

This file contains statistical summaries of distributions of such averages for each indicator and a selection of 
years (1990, 1995, 2000, 2005, 2010, 2014, 2019, 2024) based on bootstrap on 1000 simulations each. For each indicator, 
estimates are only provided for the subset of the previously listed years for which indicator data is available. 
In addition, indicators that only have data for a single area are not included as the area-weighted average would be 
identical to the original indicator data. 

It is important to note that these calculations were run without imputing missing values. 
As a consequence, the data contained here can not be directly interpreted as a continuous time series because area-weighted
averages for each year are calculated based only on the subset of areas for which indicator data is available. 


************************
** Column definitions **
************************

id = Integer identifier for the indicator. Used primarily for internal linkages in the database and
	iterative operations in code. 

name = Norwegian name of the indicator. Consistent with usage on https://www.naturindeks.no/.

indexArea = area for which the weighted average was calculated. Only the whole of Norway (= "wholeArea") is included here.
	
year_t = Calendar year to which the NI value pertains. Equivalent to the year of indicator data that was used for calculations.

q025 = 2.5% quantile of the distribution of calculated area-weighed averages. Corresponds to lower bound of 95% confidence interval. 

median = median (= 50% quantile) of the distribution of calculated area-weighed averages.

q975 = 97.5 % quantile of the distribution of calculated area-weighed averages. Corresponds to upper bound of 95% confidence interval. 

displacement = statistical displacement that occurred during calculation via the NI framework. Values deviating substantially from 
	0 in either direction indicate that truncation has shifted the mean value of the distribution considerably, and that said mean
	value therefore has to be interpreted with caution. 

Imputations = whether (1) or not (0) imputation has been used to estimated missing values. This was not done here, so all values are 0.

data_singleArea = whether (TRUE) or not (FALSE) the indicator only has data for one area. No longer relevant filtering variable that
	can be ignored as indicators with data for single areas only were already dropped. 


-------------------
CITATION
-------------------

This data package (all four files) is published under a CC_BY 4.0 license (see here for complete terms: https://creativecommons.org/licenses/by/4.0/).

When presenting or re-using the data, it should be cited as: 

Norwegian Environmental Agency (2025). NI2025: Indicator Data [Data set]. https://doi.org/10.21345/y790-v762.


Use the same citation for subsets of the data containing only single indicators and the complete datasets
containing all indicators.
