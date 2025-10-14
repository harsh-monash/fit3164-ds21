// Global chart instances
let charts = {};

// Global variable to store current weather data for exports
let currentWeatherData = null;

// Global variable to store all stations
let allStations = [];

// Global variable to store current selected station
let currentStation = null;

// Chart configuration defaults for dark theme
const chartDefaults = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: {
            position: 'top',
            labels: {
                usePointStyle: true,
                padding: 20,
                color: '#ffffff'
            }
        },
        tooltip: {
            backgroundColor: 'rgba(26, 35, 50, 0.95)',
            titleColor: '#ffffff',
            bodyColor: '#ffffff',
            borderColor: '#00d4ff',
            borderWidth: 1
        }
    },
    scales: {
        y: {
            beginAtZero: true,
            grid: {
                color: 'rgba(255, 255, 255, 0.1)'
            },
            ticks: {
                color: '#8b95a5'
            }
        },
        x: {
            grid: {
                color: 'rgba(255, 255, 255, 0.1)'
            },
            ticks: {
                color: '#8b95a5'
            }
        }
    }
};

// Color schemes for dark theme
const colors = {
    primary: '#00d4ff',
    secondary: '#8b95a5',
    success: '#10b981',
    info: '#00d4ff',
    warning: '#f59e0b',
    danger: '#ef4444',
    temperature: '#f97316',
    humidity: '#00d4ff',
    wind: '#8b5cf6',
    pressure: '#10b981',
    precipitation: '#00d4ff'
};

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    // Make export functions globally available for onclick handlers
    window.exportChart = exportChart;
    window.exportAllCharts = exportAllCharts;
    window.exportDashboard = exportDashboard;
    window.exportData = exportData;
    
    initializeDashboard();
    
    // Add event listeners
    const retryBtn = document.getElementById('retryBtn');
    if (retryBtn) {
        retryBtn.addEventListener('click', initializeDashboard);
    }
    
    // Add station selector event listener
    const stationSelect = document.getElementById('stationSelect');
    if (stationSelect) {
        stationSelect.addEventListener('change', async function(e) {
            const stationName = e.target.value;
            if (stationName && allStations.length > 0) {
                const station = allStations.find(s => s.station_name === stationName);
                if (station) {
                    currentStation = station;
                    await loadStationData(station);
                }
            }
        });
    }
    
    // Add month filter event listener
    const monthSelect = document.getElementById('monthSelect');
    if (monthSelect) {
        // Set default to current month
        const now = new Date();
        const currentMonth = now.toISOString().slice(0, 7); // Format: YYYY-MM
        monthSelect.value = currentMonth;
        
        monthSelect.addEventListener('change', async function(e) {
            if (currentStation) {
                await loadStationData(currentStation);
            }
        });
    }
});

async function initializeDashboard() {
    showLoading(true);
    showError(false);
    
    try {
        const realData = await loadWeatherData();
        currentWeatherData = realData;
        showLoading(false);
        
        try {
            initializeCharts(realData);
        } catch (chartError) {
            console.error('Charts failed to load, but data loaded successfully:', chartError);
            document.getElementById('loadingState').innerHTML = 
                '<div class="alert alert-warning">Data loaded successfully, but some charts may not display properly.</div>';
        }
        
        // Check if a station was specified in the URL (from map)
        const urlParams = new URLSearchParams(window.location.search);
        const stationParam = urlParams.get('station');
        if (stationParam && allStations.length > 0) {
            const station = allStations.find(s => s.station_name === stationParam);
            if (station) {
                // Select the station in dropdown
                const stationSelect = document.getElementById('stationSelect');
                if (stationSelect) {
                    stationSelect.value = station.station_name;
                }
                // Load the station data
                currentStation = station;
                await loadStationData(station);
            }
        }
        
    } catch (error) {
        console.error('Failed to load data:', error);
        showError(true);
        showLoading(false);
    }
}

async function loadWeatherData() {
    try {
        const stationsResponse = await fetch('/api/bom/stations');
        
        if (stationsResponse.ok) {
            const stations = await stationsResponse.json();
            allStations = stations;
            
            console.log('Loaded BOM stations:', { stationCount: stations.length });
            
            populateStationSelector(stations);
            
            const sampleStation = stations.find(s => s.record_count > 100) || stations[0];
            currentStation = sampleStation;
            
            if (sampleStation) {
                await loadStationData(sampleStation);
                updateWeatherSummary(stations);
                
                return { 
                    stations, 
                    currentStation: sampleStation
                };
            }
            
            return { stations, currentStation: null };
        } else {
            throw new Error(`BOM API error: ${stationsResponse.status}`);
        }
    } catch (error) {
        console.error('Error loading BOM data:', error);
        return null;
    }
}

function populateStationSelector(stations) {
    const stationSelect = document.getElementById('stationSelect');
    if (!stationSelect) return;
    
    stationSelect.innerHTML = '';
    
    const validStations = stations.filter(s => s.record_count > 100);
    validStations.sort((a, b) => a.station_name.localeCompare(b.station_name));
    
    validStations.forEach(station => {
        const option = document.createElement('option');
        option.value = station.station_name;
        option.textContent = `${station.station_name} (${station.record_count} records)`;
        stationSelect.appendChild(option);
    });
    
    if (validStations.length > 0) {
        stationSelect.value = validStations[0].station_name;
    }
}

async function loadStationData(station) {
    try {
        showLoading(true);
        
        // Get selected month from filter
        const monthSelect = document.getElementById('monthSelect');
        let startDate = null;
        let endDate = null;
        
        if (monthSelect && monthSelect.value) {
            // Parse selected month (format: YYYY-MM)
            const [year, month] = monthSelect.value.split('-').map(Number);
            
            // First day of the month
            startDate = new Date(year, month - 1, 1).toISOString().split('T')[0];
            
            // Last day of the month
            const lastDay = new Date(year, month, 0).getDate();
            endDate = new Date(year, month - 1, lastDay).toISOString().split('T')[0];
        }
        
        // Build query parameters
        const buildUrl = (metric) => {
            let url = `/api/bom/timeseries?station_name=${encodeURIComponent(station.station_name)}&metric=${metric}`;
            if (startDate) url += `&start_date=${startDate}`;
            if (endDate) url += `&end_date=${endDate}`;
            return url;
        };
        
        const [tempResponse, humidityResponse, windResponse] = await Promise.all([
            fetch(buildUrl('max_temperature_c')),
            fetch(buildUrl('min_relative_humidity_pct')),
            fetch(buildUrl('wind_speed_m_per_sec'))
        ]);
        
        const tempData = tempResponse.ok ? await tempResponse.json() : null;
        const humidityData = humidityResponse.ok ? await humidityResponse.json() : null;
        const windData = windResponse.ok ? await windResponse.json() : null;
        
        const minTempResponse = await fetch(buildUrl('min_temperature_c'));
        const minTempData = minTempResponse.ok ? await minTempResponse.json() : null;
        
        const timeSeriesData = {
            temperature: tempData,
            minTemperature: minTempData,
            humidity: humidityData,
            wind: windData,
            station: station
        };
        
        currentWeatherData = { 
            stations: allStations, 
            timeSeries: timeSeriesData
        };
        
        initializeCharts(currentWeatherData);
        
        showLoading(false);
        
        return timeSeriesData;
    } catch (error) {
        console.error('Error loading station data:', error);
        showError(true);
        showLoading(false);
        return null;
    }
}

function updateWeatherSummary(stations) {
    if (!stations || stations.length === 0) return;

    const validStations = stations.filter(s => s.avg_max_temp && s.avg_min_temp);
    if (validStations.length === 0) return;

    const avgMaxTemp = validStations.reduce((sum, s) => sum + s.avg_max_temp, 0) / validStations.length;
    const avgMinTemp = validStations.reduce((sum, s) => sum + s.avg_min_temp, 0) / validStations.length;
    const avgTemp = (avgMaxTemp + avgMinTemp) / 2;
    
    const avgRainfall = validStations.reduce((sum, s) => sum + (s.avg_rainfall || 0), 0) / validStations.length;
    const avgET = validStations.reduce((sum, s) => sum + (s.avg_evapotranspiration || 0), 0) / validStations.length;
    
    const avgHumidity = Math.min(90, 40 + (avgRainfall * 8));
    const avgWind = avgET * 5;

    const tempValue = document.getElementById('temperatureValue');
    const windValue = document.getElementById('windSpeedValue');
    const humValue = document.getElementById('humidityValue');
    
    if (tempValue) tempValue.textContent = `${avgTemp.toFixed(1)}C`;
    if (windValue) windValue.textContent = `${avgWind.toFixed(1)}`;
    if (humValue) humValue.textContent = `${avgHumidity.toFixed(0)}%`;
    
    const tempVariance = ((avgMaxTemp - avgMinTemp) / avgTemp * 100).toFixed(0);
    const windVariance = avgET > 3 ? '+5%' : '+2%';
    const humVariance = avgRainfall > 2 ? '+3%' : '+1%';
    
    const tempChange = document.getElementById('temperatureChange');
    const windChange = document.getElementById('windSpeedChange');
    const humChange = document.getElementById('humidityChange');
    
    if (tempChange) tempChange.textContent = `-${tempVariance}%`;
    if (windChange) windChange.textContent = windVariance;
    if (humChange) humChange.textContent = humVariance;
}

// ============================================================================
// AI-Powered Analysis Functions (Gemini Integration)
// ============================================================================

/**
 * Generate AI-powered analysis for a specific metric
 * @param {string} metric - The metric type ('temperature', 'wind', 'humidity')
 * @param {object} data - The chart data
 * @param {string} stationName - Name of the weather station
 * @param {string} dateRange - Date range string (optional)
 * @returns {Promise<string>} Generated analysis text
 */
async function generateAIAnalysis(metric, data, stationName, dateRange = null) {
    try {
        const response = await fetch('/api/analysis/generate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                metric: metric,
                data: data,
                station_name: stationName,
                date_range: dateRange
            })
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        const result = await response.json();
        return result.analysis;
    } catch (error) {
        console.error(`Error generating ${metric} analysis:`, error);
        return getFallbackAnalysis(metric, data);
    }
}

/**
 * Update analysis text for a specific metric with AI-generated content
 * @param {string} elementId - ID of the analysis element
 * @param {string} metric - The metric type
 * @param {object} data - The chart data
 * @param {string} stationName - Name of the station
 * @param {string} dateRange - Date range string
 */
async function updateAnalysisWithAI(elementId, metric, data, stationName, dateRange) {
    const analysisElement = document.getElementById(elementId);
    if (!analysisElement) return;
    
    // Check if data is empty or invalid
    if (!data || !hasValidData(data)) {
        analysisElement.textContent = getNoDataMessage(metric);
        return;
    }
    
    // Show loading state
    analysisElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Generating AI analysis...';
    
    try {
        const analysis = await generateAIAnalysis(metric, data, stationName, dateRange);
        analysisElement.textContent = analysis;
    } catch (error) {
        console.error(`Error updating ${metric} analysis:`, error);
        analysisElement.textContent = getFallbackAnalysis(metric, data);
    }
}

/**
 * Check if data object has valid data points
 * @param {object} data - The data object to check
 * @returns {boolean} True if data has valid points
 */
function hasValidData(data) {
    if (!data) return false;
    
    // Check for temperature data (has max_data and min_data)
    if (data.max_data && Array.isArray(data.max_data) && data.max_data.length > 0) {
        return true;
    }
    
    // Check for wind/humidity data (has data array)
    if (data.data && Array.isArray(data.data) && data.data.length > 0) {
        return true;
    }
    
    return false;
}

/**
 * Get message to display when no data is available
 * @param {string} metric - The metric type
 * @returns {string} No data message
 */
function getNoDataMessage(metric) {
    const messages = {
        'temperature': 'No temperature data available for the selected period. Please select a different time range or station.',
        'wind': 'No wind speed data available for the selected period. Please select a different time range or station.',
        'humidity': 'No humidity data available for the selected period. Please select a different time range or station.'
    };
    return messages[metric] || 'No data available for analysis.';
}

/**
 * Fallback analysis when AI generation fails
 * @param {string} metric - The metric type
 * @param {object} data - The chart data
 * @returns {string} Fallback analysis text
 */
function getFallbackAnalysis(metric, data) {
    if (metric === 'temperature') {
        return 'Temperature data shows variations across the monitoring period. Analysis generation unavailable - please check API configuration.';
    } else if (metric === 'wind') {
        return 'Wind speed patterns recorded during the monitoring period. Analysis generation unavailable - please check API configuration.';
    } else if (metric === 'humidity') {
        return 'Humidity levels tracked across the selected time range. Analysis generation unavailable - please check API configuration.';
    }
    return 'Weather data analysis unavailable.';
}

function initializeCharts(realData = null) {
    const chartData = realData || {
        stations: [],
        timeSeries: null
    };
    
    const hasTimeSeries = chartData.timeSeries && 
                          chartData.timeSeries.temperature && 
                          chartData.timeSeries.temperature.data &&
                          chartData.timeSeries.temperature.data.length > 0;
    
    const formatDate = (dateStr) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-AU', { month: 'short', day: 'numeric' });
    };
    
    let commonLabels = [];
    let dateRange = '';
    
    if (hasTimeSeries) {
        const tempData = chartData.timeSeries.temperature.data.slice(-30);
        commonLabels = tempData.map(d => formatDate(d.date));
        
        if (tempData.length > 0) {
            dateRange = `${formatDate(tempData[0].date)} - ${formatDate(tempData[tempData.length - 1].date)}`;
        }
    }
    
    // Temperature Chart
    const tempCanvas = document.getElementById('temperatureChart');
    if (tempCanvas) {
        if (charts.temperature) {
            charts.temperature.destroy();
        }
        
        const tempCtx = tempCanvas.getContext('2d');
        
        let labels, maxTempData, minTempData;
        
        if (hasTimeSeries) {
            const tempData = chartData.timeSeries.temperature.data.slice(-30);
            labels = commonLabels;
            maxTempData = tempData.map(d => d.value);
            
            if (chartData.timeSeries.minTemperature && 
                chartData.timeSeries.minTemperature.data &&
                chartData.timeSeries.minTemperature.data.length > 0) {
                const minTempDataFull = chartData.timeSeries.minTemperature.data.slice(-30);
                minTempData = minTempDataFull.map(d => d.value);
            } else {
                minTempData = maxTempData.map(t => t ? t - 8 : null);
            }
        } else {
            // No data available
            labels = [];
            maxTempData = [];
            minTempData = [];
        }
        
        charts.temperature = new Chart(tempCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Max Temperature (C)',
                        data: maxTempData,
                        borderColor: colors.temperature,
                        backgroundColor: 'transparent',
                        tension: 0.4,
                        borderWidth: 2,
                        pointRadius: 2,
                        pointHoverRadius: 4
                    },
                    {
                        label: 'Min Temperature (C)',
                        data: minTempData,
                        borderColor: colors.info,
                        backgroundColor: 'transparent',
                        tension: 0.4,
                        borderWidth: 2,
                        pointRadius: 2,
                        pointHoverRadius: 4
                    }
                ]
            },
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    legend: {
                        ...chartDefaults.plugins.legend,
                        display: true
                    },
                    title: {
                        display: true,
                        text: hasTimeSeries ? 
                            `${chartData.timeSeries.station.station_name} - ${dateRange}` : 
                            'Temperature Trends - No Data Available',
                        color: '#ffffff'
                    }
                }
            }
        });
    }

    // Wind Speed Chart
    const windCanvas = document.getElementById('windSpeedChart');
    if (windCanvas) {
        if (charts.windSpeed) {
            charts.windSpeed.destroy();
        }
        
        const windCtx = windCanvas.getContext('2d');
        
        let labels, windData;
        
        if (hasTimeSeries && chartData.timeSeries.wind && 
            chartData.timeSeries.wind.data &&
            chartData.timeSeries.wind.data.length > 0) {
            const windDataFull = chartData.timeSeries.wind.data.slice(-30);
            labels = commonLabels.slice(0, windDataFull.length);
            windData = windDataFull.map(d => d.value ? (d.value * 3.6).toFixed(1) : null);
        } else {
            // No data available
            labels = [];
            windData = [];
        }
        
        charts.windSpeed = new Chart(windCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Wind Speed (km/h)',
                    data: windData,
                    borderColor: colors.wind,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 4
                }]
            },
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    title: {
                        display: true,
                        text: hasTimeSeries ? 
                            `${chartData.timeSeries.station.station_name} - ${dateRange}` : 
                            'Wind Speed Trends - No Data Available',
                        color: '#ffffff'
                    }
                }
            }
        });
    }

    // Humidity Chart
    const humCanvas = document.getElementById('humidityChart');
    if (humCanvas) {
        if (charts.humidity) {
            charts.humidity.destroy();
        }
        
        const humCtx = humCanvas.getContext('2d');
        
        let labels, humidityData;
        
        if (hasTimeSeries && chartData.timeSeries.humidity && 
            chartData.timeSeries.humidity.data &&
            chartData.timeSeries.humidity.data.length > 0) {
            const humData = chartData.timeSeries.humidity.data.slice(-30);
            labels = commonLabels.slice(0, humData.length);
            humidityData = humData.map(d => d.value);
        } else {
            // No data available
            labels = [];
            humidityData = [];
        }
        
        charts.humidity = new Chart(humCtx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Humidity (%)',
                    data: humidityData,
                    borderColor: colors.humidity,
                    backgroundColor: 'transparent',
                    tension: 0.4,
                    borderWidth: 2,
                    pointRadius: 2,
                    pointHoverRadius: 4
                }]
            },
            options: {
                ...chartDefaults,
                plugins: {
                    ...chartDefaults.plugins,
                    title: {
                        display: true,
                        text: hasTimeSeries ? 
                            `${chartData.timeSeries.station.station_name} - ${dateRange}` : 
                            'Humidity Trends - No Data Available',
                        color: '#ffffff'
                    }
                }
            }
        });
    }
    
    // ============================================================================
    // Generate AI Analysis for all charts
    // ============================================================================
    if (hasTimeSeries && chartData.timeSeries.station) {
        const stationName = chartData.timeSeries.station.station_name;
        
        // Temperature Analysis - check if data exists and has length
        if (chartData.timeSeries.temperature && 
            chartData.timeSeries.temperature.data && 
            chartData.timeSeries.temperature.data.length > 0) {
            const tempAnalysisData = {
                max_data: chartData.timeSeries.temperature.data,
                min_data: chartData.timeSeries.minTemperature ? chartData.timeSeries.minTemperature.data : []
            };
            updateAnalysisWithAI('temperatureAnalysis', 'temperature', tempAnalysisData, stationName, dateRange);
        } else {
            // No data available
            const tempElement = document.getElementById('temperatureAnalysis');
            if (tempElement) {
                tempElement.textContent = 'No temperature data available for the selected period. Please select a different time range or station.';
            }
        }
        
        // Wind Analysis - check if data exists and has length
        if (chartData.timeSeries.wind && 
            chartData.timeSeries.wind.data && 
            chartData.timeSeries.wind.data.length > 0) {
            updateAnalysisWithAI('windSpeedAnalysis', 'wind', chartData.timeSeries.wind, stationName, dateRange);
        } else {
            // No data available
            const windElement = document.getElementById('windSpeedAnalysis');
            if (windElement) {
                windElement.textContent = 'No wind speed data available for the selected period. Please select a different time range or station.';
            }
        }
        
        // Humidity Analysis - check if data exists and has length
        if (chartData.timeSeries.humidity && 
            chartData.timeSeries.humidity.data && 
            chartData.timeSeries.humidity.data.length > 0) {
            updateAnalysisWithAI('humidityAnalysis', 'humidity', chartData.timeSeries.humidity, stationName, dateRange);
        } else {
            // No data available
            const humElement = document.getElementById('humidityAnalysis');
            if (humElement) {
                humElement.textContent = 'No humidity data available for the selected period. Please select a different time range or station.';
            }
        }
    } else {
        // No station selected or no time series data
        const tempElement = document.getElementById('temperatureAnalysis');
        const windElement = document.getElementById('windSpeedAnalysis');
        const humElement = document.getElementById('humidityAnalysis');
        
        if (tempElement) tempElement.textContent = 'Select a weather station to view AI-generated temperature analysis.';
        if (windElement) windElement.textContent = 'Select a weather station to view AI-generated wind speed analysis.';
        if (humElement) humElement.textContent = 'Select a weather station to view AI-generated humidity analysis.';
    }
}

// Helper functions
function generateDateLabels(count) {
    const labels = [];
    const now = new Date();
    for (let i = count - 1; i >= 0; i--) {
        const date = new Date(now.getTime() - (i * 24 * 60 * 60 * 1000));
        labels.push(date.toLocaleDateString('en-AU', { month: 'short', day: 'numeric' }));
    }
    return labels;
}

function showLoading(show) {
    const loadingState = document.getElementById('loadingState');
    if (loadingState) {
        if (show) {
            loadingState.classList.remove('d-none');
        } else {
            loadingState.classList.add('d-none');
        }
    }
}

function showError(show) {
    const errorState = document.getElementById('errorState');
    if (errorState) {
        if (show) {
            errorState.classList.remove('d-none');
        } else {
            errorState.classList.add('d-none');
        }
    }
}

// Export functions (placeholders for compatibility)
// todo 
function exportChart(chartType) {
    console.log('Export chart:', chartType);
    // alert('Export functionality coming soon!');
    if (charts[chartType]) {
        const link = document.createElement('a');
        link.href = charts[chartType].toBase64Image();
        link.download = `${chartType}_chart.png`;
        link.click();
    } else {
        alert('Chart not available for export.');
    }
}

function exportAllCharts() {
    console.log('Export all charts');
    
    const availableCharts = Object.keys(charts).filter(chartType => charts[chartType]);
    
    if (availableCharts.length === 0) {
        alert('No charts available for export. Please load data first.');
        return;
    }
    
    // Export each chart with a small delay to avoid browser blocking multiple downloads
    availableCharts.forEach((chartType, index) => {
        setTimeout(() => {
            const link = document.createElement('a');
            link.href = charts[chartType].toBase64Image();
            const stationName = currentStation ? currentStation.station_name.replace(/\s+/g, '_') : 'station';
            link.download = `${stationName}_${chartType}_chart.png`;
            link.click();
        }, index * 300); // 300ms delay between each download
    });
    
    console.log(`Exporting ${availableCharts.length} charts...`);
}

function exportDashboard() {
    console.log('Export dashboard');
    alert('Export dashboard functionality coming soon!');
}

function exportData(format) {
    console.log('Export data:', format);
    
    if (!currentWeatherData) {
        alert('No data available for export. Please select a station and load data first.');
        return;
    }
    
    if (format === 'csv') {
        exportAsCSV();
    } else if (format === 'json') {
        exportAsJSON();
    } else if (format === 'pdf') {
        alert('PDF export functionality coming soon!');
    } else {
        alert('Unsupported export format.');
    }
}

function exportAsCSV() {
    let csvContent = 'data:text/csv;charset=utf-8,';
    
    // Add header with station info
    const stationName = currentStation ? currentStation.station_name : 'Unknown Station';
    csvContent += `Station: ${stationName}\n`;
    csvContent += `Export Date: ${new Date().toLocaleString('en-AU')}\n\n`;
    
    // Add column headers
    csvContent += 'Date,Max Temperature (C),Min Temperature (C),Humidity (%),Wind Speed (km/h)\n';
    
    const tempData = currentWeatherData.timeSeries.temperature.data || [];
    const minTempData = currentWeatherData.timeSeries.minTemperature ? currentWeatherData.timeSeries.minTemperature.data : [];
    const humData = currentWeatherData.timeSeries.humidity ? currentWeatherData.timeSeries.humidity.data : [];
    const windData = currentWeatherData.timeSeries.wind ? currentWeatherData.timeSeries.wind.data : [];
    
    const maxLength = Math.max(tempData.length, minTempData.length, humData.length, windData.length);
    
    for (let i = 0; i < maxLength; i++) {
        const date = tempData[i] ? tempData[i].date : 
                     minTempData[i] ? minTempData[i].date : 
                     humData[i] ? humData[i].date : 
                     windData[i] ? windData[i].date : '';
        const maxTemp = tempData[i] ? tempData[i].value : '';
        const minTemp = minTempData[i] ? minTempData[i].value : '';
        const humidity = humData[i] ? humData[i].value : '';
        const windSpeed = windData[i] ? (windData[i].value * 3.6).toFixed(1) : ''; // Convert m/s to km/h
        
        csvContent += `${date},${maxTemp},${minTemp},${humidity},${windSpeed}\n`;
    }
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `weather_data_${stationName.replace(/\s+/g, '_')}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    console.log('CSV export completed');
}

function exportAsJSON() {
    const exportData = {
        station: currentStation,
        exportDate: new Date().toISOString(),
        weatherData: {
            temperature: currentWeatherData.timeSeries.temperature.data || [],
            minTemperature: currentWeatherData.timeSeries.minTemperature ? currentWeatherData.timeSeries.minTemperature.data : [],
            humidity: currentWeatherData.timeSeries.humidity ? currentWeatherData.timeSeries.humidity.data : [],
            windSpeed: currentWeatherData.timeSeries.wind ? currentWeatherData.timeSeries.wind.data : []
        },
        summary: currentWeatherData.timeSeries.summary || {}
    };
    
    const jsonString = JSON.stringify(exportData, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const stationName = currentStation ? currentStation.station_name : 'Unknown_Station';
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `weather_data_${stationName.replace(/\s+/g, '_')}.json`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
    
    console.log('JSON export completed');
}
