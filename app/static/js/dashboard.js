/**
 * Weather Dashboard JavaScript - Main Application Logic
 *
 * CODE REVIEW SUMMARY:
 * ✅ GOOD PRACTICES:
 * - Well-structured modular functions
 * - Proper error handling with try-catch blocks
 * - Good use of async/await for API calls
 * - Consistent naming conventions
 * - Proper DOM manipulation with modern APIs
 * - Good separation of concerns (map, search, filtering)
 *
 * ⚠️ AREAS FOR IMPROVEMENT:
 * - File is extremely large (1227 lines) - should be split into modules
 * - Some functions are very long and do multiple things
 * - Missing JSDoc comments for many functions
 * - Global variables could be better encapsulated
 * - No input validation for user inputs
 * - Missing loading states for long operations
 * - Could benefit from TypeScript for better type safety
 *
 * 🔧 RECOMMENDATIONS:
 * - Split into separate modules: map.js, search.js, api.js, utils.js
 * - Add comprehensive JSDoc documentation
 * - Implement proper error boundaries
 * - Add input validation and sanitization
 * - Use modern JavaScript features (optional chaining, nullish coalescing)
 * - Add unit tests for utility functions
 * - Implement proper state management
 * - Add performance monitoring
 * - Consider using a framework like Vue.js or React for better maintainability
 */

// Minimal dashboard bootstrap: fetch statistics and stations and populate the page
const API_BASE = '/api';
let weatherMap = null;
let dashboardMarkersLayer = null; // Renamed to avoid conflict with map.js
let heatmapLayer = null;
let currentFilteredData = null;

// Global error handler
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
});

document.addEventListener('DOMContentLoaded', () => {
    loadStatistics();
    loadStations();
    
    // Only initialize map if weatherMap element exists (dashboard.html)
    if (document.getElementById('weatherMap')) {
        initializeMap();
    }
    
    initializeSearch();
    initializeFeedback();
    initializeFiltering();
});

function initializeMap() {
	// Initialize the Leaflet map centered on NSW, Australia
	weatherMap = L.map('weatherMap').setView([-32.0, 147.0], 6);
	
	// Add OpenStreetMap tiles
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		attribution: '© OpenStreetMap contributors'
	}).addTo(weatherMap);
	
	// Create layer groups
	dashboardMarkersLayer = L.layerGroup().addTo(weatherMap);
	
	// Add layer control
	const baseLayers = {
		"OpenStreetMap": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
			attribution: '© OpenStreetMap contributors'
		})
	};
	
	const overlayLayers = {
		"Weather Stations": dashboardMarkersLayer
	};
	
	L.control.layers(baseLayers, overlayLayers).addTo(weatherMap);
	
	// Add legend control
	addLegend();
	
	// Load stations on map
	loadStationsOnMap();
}

async function loadStationsOnMap() {
	try {
		// Clear existing markers
		if (dashboardMarkersLayer) {
			dashboardMarkersLayer.clearLayers();
		}
		
		const resp = await fetch(`${API_BASE}/bom/stations`);
		if (!resp.ok) throw new Error('Failed to load stations for map');
		const stations = await resp.json();
		
		stations.forEach(station => {
			if (station.latitude && station.longitude) {
				const marker = L.marker([station.latitude, station.longitude]);
				
				// Create popup content
				const popupContent = `
					<div class="popup-station-name">${station.station_name}</div>
					<div><strong>Records:</strong> ${(station.record_count || 0).toLocaleString()}</div>
					<div><strong>State:</strong> ${station.state || 'N/A'}</div>
					<div><strong>Avg ET:</strong> ${station.avg_evapotranspiration ? station.avg_evapotranspiration.toFixed(2) + ' mm' : 'N/A'}</div>
				`;
				
				marker.bindPopup(popupContent);
				dashboardMarkersLayer.addLayer(marker);
			}
		});
	} catch (err) {
		console.error('Failed to load stations on map:', err);
	}
}

function updateMap() {
	const selectedMetric = document.getElementById('mapMetric')?.value;
	console.log('Updating map with metric:', selectedMetric);
	// Reload the stations with the selected metric
	loadStationsOnMap();
}

// Heat map visualization functions
function createHeatmapData(data, variable = 'temperature') {
    const heatmapData = [];
    const locationData = {};
    
    // Group data by location and calculate averages
    data.forEach(record => {
        if (record.latitude && record.longitude && record.value !== null && record.value !== undefined) {
            const key = `${record.latitude},${record.longitude}`;
            if (!locationData[key]) {
                locationData[key] = {
                    lat: record.latitude,
                    lng: record.longitude,
                    values: [],
                    location: record.location
                };
            }
            locationData[key].values.push(parseFloat(record.value));
        }
    });
    
    // Calculate averages and create heatmap points
    Object.values(locationData).forEach(location => {
        const average = location.values.reduce((sum, val) => sum + val, 0) / location.values.length;
        heatmapData.push({
            lat: location.lat,
            lng: location.lng,
            value: average,
            location: location.location,
            count: location.values.length
        });
    });
    
    return heatmapData;
}

function getHeatmapColor(value, variable = 'temperature') {
    // Define color gradients based on variable type
    const gradients = {
        temperature: [
            { threshold: -10, color: '#0000ff' }, // Very cold - Blue
            { threshold: 0, color: '#0080ff' },   // Cold - Light blue
            { threshold: 10, color: '#00ffff' }, // Cool - Cyan
            { threshold: 20, color: '#80ff80' }, // Mild - Light green
            { threshold: 25, color: '#ffff00' }, // Warm - Yellow
            { threshold: 30, color: '#ff8000' }, // Hot - Orange
            { threshold: 35, color: '#ff0000' }  // Very hot - Red
        ],
        rainfall: [
            { threshold: 0, color: '#ffffff' },   // No rain - White
            { threshold: 1, color: '#e6f3ff' },   // Light rain - Very light blue
            { threshold: 5, color: '#b3d9ff' },   // Moderate rain - Light blue
            { threshold: 10, color: '#80bfff' }, // Heavy rain - Medium blue
            { threshold: 25, color: '#4d94ff' }, // Very heavy - Blue
            { threshold: 50, color: '#0066cc' }, // Extreme - Dark blue
            { threshold: 100, color: '#004080' } // Torrential - Very dark blue
        ],
        humidity: [
            { threshold: 0, color: '#ffcccc' },   // Very dry - Light red
            { threshold: 20, color: '#ff9999' },  // Dry - Light red
            { threshold: 40, color: '#ff6666' },  // Moderate - Red
            { threshold: 60, color: '#ffff99' },  // Comfortable - Light yellow
            { threshold: 70, color: '#99ff99' },  // Humid - Light green
            { threshold: 80, color: '#66cc66' },  // Very humid - Green
            { threshold: 90, color: '#339933' }   // Extremely humid - Dark green
        ]
    };
    
    const gradient = gradients[variable] || gradients.temperature;
    
    for (let i = gradient.length - 1; i >= 0; i--) {
        if (value >= gradient[i].threshold) {
            return gradient[i].color;
        }
    }
    
    return gradient[0].color; // Default to first color if below minimum
}

function updateHeatmapLayer(data, variable = 'temperature') {
    // Remove existing heatmap layer
    if (heatmapLayer) {
        weatherMap.removeLayer(heatmapLayer);
        heatmapLayer = null;
    }
    
    if (!data || data.length === 0) {
        return;
    }
    
    const heatmapData = createHeatmapData(data, variable);
    
    // Create heatmap layer using Leaflet.heat plugin
    const heatPoints = heatmapData.map(point => [
        point.lat,
        point.lng,
        point.value
    ]);
    
    heatmapLayer = L.heatLayer(heatPoints, {
        radius: 25,
        blur: 15,
        maxZoom: 10,
        max: Math.max(...heatmapData.map(p => p.value)),
        gradient: createHeatmapGradient(variable)
    }).addTo(weatherMap);
    
    // Add custom markers for each data point with color coding
    const dataMarkers = L.layerGroup();
    
    heatmapData.forEach(point => {
        const color = getHeatmapColor(point.value, variable);
        const marker = L.circleMarker([point.lat, point.lng], {
            color: color,
            fillColor: color,
            fillOpacity: 0.8,
            radius: 8,
            weight: 2
        });
        
        const popupContent = `
            <div class="heatmap-popup">
                <h6>${point.location || 'Location'}</h6>
                <div><strong>${variable.charAt(0).toUpperCase() + variable.slice(1)}:</strong> ${point.value.toFixed(2)}</div>
                <div><strong>Records:</strong> ${point.count}</div>
                <div><strong>Coordinates:</strong> ${point.lat.toFixed(4)}, ${point.lng.toFixed(4)}</div>
            </div>
        `;
        
        marker.bindPopup(popupContent);
        dataMarkers.addLayer(marker);
    });
    
    // Add data markers to map
    dataMarkers.addTo(weatherMap);
    
    // Store reference for cleanup
    heatmapLayer.dataMarkers = dataMarkers;
}

function createHeatmapGradient(variable = 'temperature') {
    const gradients = {
        temperature: {
            0.0: '#0000ff',   // Very cold
            0.2: '#0080ff',   // Cold
            0.4: '#00ffff',   // Cool
            0.6: '#80ff80',   // Mild
            0.8: '#ffff00',   // Warm
            1.0: '#ff0000'    // Very hot
        },
        rainfall: {
            0.0: '#ffffff',   // No rain
            0.2: '#e6f3ff',   // Light rain
            0.4: '#b3d9ff',   // Moderate rain
            0.6: '#80bfff',   // Heavy rain
            0.8: '#4d94ff',   // Very heavy
            1.0: '#004080'    // Torrential
        },
        humidity: {
            0.0: '#ffcccc',   // Very dry
            0.2: '#ff9999',   // Dry
            0.4: '#ff6666',   // Moderate
            0.6: '#ffff99',   // Comfortable
            0.8: '#99ff99',   // Humid
            1.0: '#339933'    // Extremely humid
        }
    };
    
    return gradients[variable] || gradients.temperature;
}

function clearHeatmapLayer() {
    if (heatmapLayer) {
        if (heatmapLayer.dataMarkers) {
            weatherMap.removeLayer(heatmapLayer.dataMarkers);
        }
        weatherMap.removeLayer(heatmapLayer);
        heatmapLayer = null;
    }
}

function updateMapWithFilteredData(data, variable = 'temperature') {
    if (!data || data.length === 0) {
        clearHeatmapLayer();
        return;
    }
    
    // Filter data to only include records with coordinates
    const geoData = data.filter(record => 
        record.latitude && record.longitude && 
        record.value !== null && record.value !== undefined
    );
    
    if (geoData.length === 0) {
        clearHeatmapLayer();
        console.warn('No geolocated data found for map visualization');
        return;
    }
    
    // Update heatmap layer
    updateHeatmapLayer(geoData, variable);
    
    // Update legend
    updateLegend(variable);
    
    // Fit map bounds to show all data points
    const bounds = L.latLngBounds(
        geoData.map(record => [record.latitude, record.longitude])
    );
    
    if (bounds.isValid()) {
        weatherMap.fitBounds(bounds, { padding: [20, 20] });
    }
}

function addLegend() {
    const legend = L.control({ position: 'bottomright' });
    
    legend.onAdd = function(map) {
        const div = L.DomUtil.create('div', 'info legend');
        div.innerHTML = `
            <div class="legend-header">
                <h6>Temperature Legend</h6>
            </div>
            <div class="legend-content">
                <div class="legend-item">
                    <span class="legend-color" style="background: #0000ff"></span>
                    <span>&lt; -10°C</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #0080ff"></span>
                    <span>-10°C to 0°C</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #00ffff"></span>
                    <span>0°C to 10°C</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #80ff80"></span>
                    <span>10°C to 20°C</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #ffff00"></span>
                    <span>20°C to 25°C</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #ff8000"></span>
                    <span>25°C to 30°C</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: #ff0000"></span>
                    <span>&gt; 30°C</span>
                </div>
            </div>
        `;
        return div;
    };
    
    legend.addTo(weatherMap);
}

function updateLegend(variable = 'temperature') {
    // Update legend based on selected variable
    const legendContent = document.querySelector('.legend-content');
    if (!legendContent) return;
    
    const legends = {
        temperature: `
            <div class="legend-item">
                <span class="legend-color" style="background: #0000ff"></span>
                <span>&lt; -10°C</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #0080ff"></span>
                <span>-10°C to 0°C</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #00ffff"></span>
                <span>0°C to 10°C</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #80ff80"></span>
                <span>10°C to 20°C</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ffff00"></span>
                <span>20°C to 25°C</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ff8000"></span>
                <span>25°C to 30°C</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ff0000"></span>
                <span>&gt; 30°C</span>
            </div>
        `,
        rainfall: `
            <div class="legend-item">
                <span class="legend-color" style="background: #ffffff"></span>
                <span>0 mm</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #e6f3ff"></span>
                <span>0-1 mm</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #b3d9ff"></span>
                <span>1-5 mm</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #80bfff"></span>
                <span>5-10 mm</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #4d94ff"></span>
                <span>10-25 mm</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #0066cc"></span>
                <span>25-50 mm</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #004080"></span>
                <span>&gt; 50 mm</span>
            </div>
        `,
        humidity: `
            <div class="legend-item">
                <span class="legend-color" style="background: #ffcccc"></span>
                <span>&lt; 20%</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ff9999"></span>
                <span>20-40%</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ff6666"></span>
                <span>40-60%</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #ffff99"></span>
                <span>60-70%</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #99ff99"></span>
                <span>70-80%</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #66cc66"></span>
                <span>80-90%</span>
            </div>
            <div class="legend-item">
                <span class="legend-color" style="background: #339933"></span>
                <span>&gt; 90%</span>
            </div>
        `
    };
    
    const legendHeader = document.querySelector('.legend-header h6');
    if (legendHeader) {
        legendHeader.textContent = `${variable.charAt(0).toUpperCase() + variable.slice(1)} Legend`;
    }
    
    legendContent.innerHTML = legends[variable] || legends.temperature;
}

function toggleMapVisualization() {
    const toggleMapBtn = document.getElementById('toggleMapBtn');
    const mapSection = document.getElementById('weatherMapSection');
    
    if (!mapSection) return;
    
    if (mapSection.style.display === 'none' || mapSection.style.display === '') {
        // Show map
        mapSection.style.display = 'block';
        toggleMapBtn.innerHTML = '<i class="fas fa-map-marked-alt"></i> Hide Map';
        toggleMapBtn.classList.remove('btn-outline-secondary');
        toggleMapBtn.classList.add('btn-secondary');
        
        // Scroll to map section
        mapSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        
        // If we have filtered data, update the map
        if (currentFilteredData && currentFilteredData.length > 0) {
            const variable = document.getElementById('variableFilter').value || 'temperature';
            updateMapWithFilteredData(currentFilteredData, variable);
        }
    } else {
        // Hide map
        mapSection.style.display = 'none';
        toggleMapBtn.innerHTML = '<i class="fas fa-map-marked-alt"></i> Show Map';
        toggleMapBtn.classList.remove('btn-secondary');
        toggleMapBtn.classList.add('btn-outline-secondary');
    }
}

function initializeSearch() {
	const searchInput = document.getElementById('topPlaceSearchInput');
	const searchResults = document.getElementById('topPlaceSearchResults');
	const clearButton = document.getElementById('topSearchClear');
	const searchResultsContainer = document.getElementById('searchResultsContainer');
	const closeResultsButton = document.getElementById('closeResults');
	const selectedLocationName = document.getElementById('selectedLocationName');
	const searchResultsContent = document.getElementById('searchResultsContent');
	
	let searchTimeout;
	
	// Search input handler
	searchInput?.addEventListener('input', (e) => {
		const query = e.target.value.trim();
		
		// Clear previous timeout
		if (searchTimeout) {
			clearTimeout(searchTimeout);
		}
		
		// Clear results if query is empty
		if (!query) {
			searchResults.innerHTML = '';
			hideSearchResults();
			return;
		}
		
		// Show results container while searching
		showSearchResults();
		searchResults.innerHTML = '<div class="list-group-item">Searching...</div>';
		
		// Debounce search requests
		searchTimeout = setTimeout(() => {
			performLocationSearch(query);
		}, 300);
	});
	
	// Clear button handler
	clearButton?.addEventListener('click', () => {
		searchInput.value = '';
		searchResults.innerHTML = '';
		hideSearchResults();
	});
	
	// Close results button handler
	closeResultsButton?.addEventListener('click', () => {
		hideSearchResults();
	});
}

function showSearchResults() {
	const container = document.getElementById('searchResultsContainer');
	container.classList.remove('search-results-hidden');
	container.classList.add('search-results-visible');
}

function hideSearchResults() {
	const container = document.getElementById('searchResultsContainer');
	container.classList.remove('search-results-visible');
	container.classList.add('search-results-hidden');
}

async function performLocationSearch(query) {
	const searchResults = document.getElementById('topPlaceSearchResults');
	
	try {
		// Use Nominatim API for OpenStreetMap geocoding
		const response = await fetch(
			`https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(query)}&countrycodes=au`
		);
		
		if (!response.ok) {
			throw new Error('Search failed');
		}
		
		const results = await response.json();
		
		// Check if no results found
		if (!results || results.length === 0) {
			searchResults.innerHTML = '<div class="list-group-item">No locations found. Try a different search term.</div>';
			return;
		}
		
		// Display results
		searchResults.innerHTML = results.map(result => `
			<button class="list-group-item list-group-item-action" data-lat="${result.lat}" data-lon="${result.lon}" data-name="${result.display_name}">
				<div class="d-flex flex-column">
					<div class="fw-bold mb-1">${result.name || result.display_name.split(',')[0]}</div>
					<small class="text-muted">${result.display_name}</small>
				</div>
			</button>
		`).join('');
		
		// Add click handlers to result items
		searchResults.querySelectorAll('.list-group-item').forEach(item => {
			item.addEventListener('click', () => {
				const lat = parseFloat(item.dataset.lat);
				const lon = parseFloat(item.dataset.lon);
				const name = item.dataset.name;
				
				selectLocation(lat, lon, name);
				// Don't clear results immediately - let the selectLocation function handle it
			});
		});
		
	} catch (error) {
		console.error('Search error:', error);
		searchResults.innerHTML = '<div class="list-group-item text-danger">Search failed. Please try again.</div>';
	}
}

async function selectLocation(lat, lon, name) {
	const selectedLocationName = document.getElementById('selectedLocationName');
	const searchResultsContent = document.getElementById('searchResultsContent');
	
	// Show the results container and update title
	showSearchResults();
	selectedLocationName.textContent = name;
	searchResultsContent.innerHTML = '<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading weather data...</div>';
	
	// Move map to location
	if (weatherMap) {
		weatherMap.setView([lat, lon], 10);
		
		// Add a temporary marker for the searched location
		const searchMarker = L.marker([lat, lon], {
			icon: L.icon({
				iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
				shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
				iconSize: [25, 41],
				iconAnchor: [12, 41],
				popupAnchor: [1, -34],
				shadowSize: [41, 41]
			})
		}).addTo(weatherMap);
		
		searchMarker.bindPopup(`<b>Searched Location</b><br>${name}`).openPopup();
	}
	
	try {
		// Get current weather data from Open-Meteo
		console.log('Fetching Open-Meteo data for:', lat, lon);
		const currentWeather = await fetchOpenMeteoData(lat, lon);
		console.log('Open-Meteo data received:', currentWeather);
		
		// Try to get nearby weather stations
		const nearbyResponse = await fetch(`${API_BASE}/weather/nearby?lat=${lat}&lng=${lon}&radius_km=50`);
		
		// Start with just the coordinates, no duplicate location name
		let resultHtml = `
			<div class="mb-3">
				<p class="mb-0 text-muted"><i class="fas fa-map-marker-alt"></i> <strong>Coordinates:</strong> ${lat.toFixed(4)}, ${lon.toFixed(4)}</p>
			</div>
		`;
		
		// Add current weather data if available
		if (currentWeather) {
			resultHtml += `
				<div class="card search-result-weather-card mb-3">
					<div class="card-header">
						<h6 class="mb-0"><i class="fas fa-cloud-sun"></i> Current Weather (Open-Meteo)</h6>
					</div>
					<div class="card-body">
						<div class="row">
							<div class="col-md-6">
								<div class="weather-metric">
									<strong>${currentWeather.temperature}°C</strong>
									<small>Temperature</small>
								</div>
								<div class="weather-metric">
									<strong>${currentWeather.humidity}%</strong>
									<small>Humidity</small>
								</div>
							</div>
							<div class="col-md-6">
								<div class="weather-metric">
									<strong>${currentWeather.windSpeed} km/h</strong>
									<small>Wind Speed</small>
								</div>
								<div class="weather-metric">
									<strong>${currentWeather.pressure} hPa</strong>
									<small>Pressure</small>
								</div>
							</div>
						</div>
						<div class="row mt-2">
							<div class="col-12">
								<div class="weather-metric">
									<strong>${currentWeather.description}</strong>
									<small>Conditions • Updated: ${currentWeather.time}</small>
								</div>
							</div>
						</div>
					</div>
				</div>
			`;
		} else {
			resultHtml += `
				<div class="alert alert-warning mb-3">
					<i class="fas fa-exclamation-triangle"></i> Current weather data not available from Open-Meteo
				</div>
			`;
		}
		
		// Add nearby weather stations section
		resultHtml += '<h6><i class="fas fa-broadcast-tower"></i> Nearby Weather Stations (within 50km)</h6>';
		
		if (nearbyResponse.ok) {
			const nearbyData = await nearbyResponse.json();
			
			if (nearbyData.stations && nearbyData.stations.length > 0) {
				resultHtml += '<div class="nearby-stations-list">';
				nearbyData.stations.slice(0, 5).forEach(station => {
					resultHtml += `
						<div class="card mb-2">
							<div class="card-body p-3">
								<h6 class="card-title mb-1">${station.name}</h6>
								<p class="card-text mb-0">
									<small class="text-muted">${station.state} • ${station.distance_km}km away</small>
								</p>
							</div>
						</div>
					`;
				});
				resultHtml += '</div>';
			} else {
				resultHtml += '<p class="text-muted">No weather stations found within 50km.</p>';
			}
		} else {
			resultHtml += '<p class="text-muted">Weather station data not available.</p>';
		}
		
		searchResultsContent.innerHTML = resultHtml;
		
	} catch (error) {
		console.error('Error fetching weather data:', error);
		searchResultsContent.innerHTML = `
			<div class="alert alert-danger">
				<h6><i class="fas fa-exclamation-circle"></i> Error Loading Data</h6>
				<p class="mb-0">Unable to load weather data for this location. Please try again.</p>
			</div>
		`;
	}
}

async function fetchOpenMeteoData(lat, lon) {
	try {
		console.log('Fetching from Open-Meteo API for coordinates:', lat, lon);
		
		// Open-Meteo API for current weather
		const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,surface_pressure,weather_code&timezone=auto`;
		console.log('API URL:', url);
		
		const response = await fetch(url);
		
		if (!response.ok) {
			console.error('Open-Meteo API response not OK:', response.status, response.statusText);
			throw new Error('Open-Meteo API failed');
		}
		
		const data = await response.json();
		console.log('Raw Open-Meteo data:', data);
		
		const current = data.current;
		
		// Weather code descriptions (WMO codes)
		const weatherDescriptions = {
			0: 'Clear sky',
			1: 'Mainly clear',
			2: 'Partly cloudy',
			3: 'Overcast',
			45: 'Fog',
			48: 'Depositing rime fog',
			51: 'Light drizzle',
			53: 'Moderate drizzle',
			55: 'Dense drizzle',
			61: 'Slight rain',
			63: 'Moderate rain',
			65: 'Heavy rain',
			71: 'Slight snow',
			73: 'Moderate snow',
			75: 'Heavy snow',
			80: 'Slight rain showers',
			81: 'Moderate rain showers',
			82: 'Violent rain showers',
			95: 'Thunderstorm',
			96: 'Thunderstorm with slight hail',
			99: 'Thunderstorm with heavy hail'
		};
		
		const processedData = {
			temperature: Math.round(current.temperature_2m * 10) / 10,
			humidity: Math.round(current.relative_humidity_2m),
			windSpeed: Math.round(current.wind_speed_10m * 10) / 10,
			pressure: Math.round(current.surface_pressure * 10) / 10,
			description: weatherDescriptions[current.weather_code] || 'Unknown',
			time: new Date(current.time).toLocaleString()
		};
		
		console.log('Processed Open-Meteo data:', processedData);
		return processedData;
		
	} catch (error) {
		console.error('Open-Meteo fetch error:', error);
		return null;
	}
}

async function loadStatistics() {
    try {
        const resp = await fetch(`${API_BASE}/bom/statistics`);
        if (!resp.ok) throw new Error('Failed to load statistics');
        const data = await resp.json();
        // BOM API returns { dataset_overview: {total_records, total_stations}, temperature: {min_average, max_average}, evapotranspiration: {average} }
        const totalRecords = data.dataset_overview?.total_records ?? 0;
        const totalStations = data.dataset_overview?.total_stations ?? 0;
        const avgTemp = data.temperature?.min_average ?? data.temperature?.max_average ?? null;
        const avgET = data.evapotranspiration?.average ?? null;
        
        // Only update if elements exist (dashboard.html specific)
        const totalRecordsEl = document.getElementById('totalRecords');
        const totalStationsEl = document.getElementById('totalStations');
        const avgTempEl = document.getElementById('avgTemp');
        const avgETEl = document.getElementById('avgET');
        
        if (totalRecordsEl) totalRecordsEl.textContent = Number(totalRecords).toLocaleString();
        if (totalStationsEl) totalStationsEl.textContent = totalStations;
        if (avgTempEl) avgTempEl.textContent = avgTemp !== null ? `${Number(avgTemp).toFixed(1)}°C` : 'N/A';
        if (avgETEl) avgETEl.textContent = avgET !== null ? `${Number(avgET).toFixed(2)} mm` : 'N/A';
        
    } catch (err) {
        console.error('Statistics load error', err);
        // Only update if elements exist
        const totalRecordsEl = document.getElementById('totalRecords');
        const totalStationsEl = document.getElementById('totalStations');
        const avgTempEl = document.getElementById('avgTemp');
        const avgETEl = document.getElementById('avgET');
        
        if (totalRecordsEl) totalRecordsEl.textContent = 'Error';
        if (totalStationsEl) totalStationsEl.textContent = 'Error';
        if (avgTempEl) avgTempEl.textContent = 'Error';
        if (avgETEl) avgETEl.textContent = 'Error';
    }
}

async function loadStations() {
	try {
		const resp = await fetch(`${API_BASE}/bom/stations`);
		if (!resp.ok) throw new Error('Failed to load stations');
		const stations = await resp.json();
		
		// Only update if elements exist (dashboard.html specific)
		const stationCountEl = document.getElementById('stationCount');
		const gridEl = document.getElementById('stationsGrid');
		
		if (stationCountEl) {
			stationCountEl.textContent = `${stations.length} stations`;
		}
		
		if (gridEl) {
			gridEl.innerHTML = stations.map(s => {
				const name = s.station_name ?? s.name ?? s.code ?? 'Unknown';
				const records = s.record_count ?? 0;
				const avgET = s.avg_evapotranspiration ?? null;
				const avgETDisplay = (avgET !== null && avgET !== undefined) ? `${Number(avgET).toFixed(2)} mm` : 'N/A';
				return `
					<div class="station-card">
						<h6>${name}</h6>
						<div class="row">
							<div class="col-6"><small class="text-muted">Records:</small><br><strong>${Number(records).toLocaleString()}</strong></div>
							<div class="col-6"><small class="text-muted">Avg ET:</small><br><strong>${avgETDisplay}</strong></div>
						</div>
				</div>
			`;
		}).join('');
		}
		
		// Initialize the collapse functionality after stations are loaded
		setTimeout(() => {
			initializeStationsCollapse();
		}, 100);
	} catch (err) {
		console.error('Stations load error', err);
		const stationCountEl = document.getElementById('stationCount');
		if (stationCountEl) {
			stationCountEl.textContent = 'Error loading stations';
		}
	}
}

// Stations collapse functionality
function initializeStationsCollapse() {
    console.log('🔧 Attempting to initialize stations collapse...');
    
    const toggleBtn = document.getElementById('toggleStationsBtn');
    const stationsGrid = document.getElementById('stationsGrid');
    const stationCount = document.getElementById('stationCount');
    
    console.log('🔍 Elements check:', {
        toggleBtn: !!toggleBtn,
        stationsGrid: !!stationsGrid,
        stationCount: !!stationCount,
        toggleBtnExists: toggleBtn !== null,
        stationsGridExists: stationsGrid !== null
    });
    
    if (!toggleBtn) {
        console.error('❌ Toggle button not found!');
        return false;
    }
    
    if (!stationsGrid) {
        console.error('❌ Stations grid not found!');
        return false;
    }
    
    // Check if already initialized
    if (toggleBtn.dataset.initialized === 'true') {
        console.log('✅ Already initialized, skipping...');
        return true;
    }
    
    console.log('🚀 Setting up click handler...');
    
    let isHidden = false;
    
    // Clear any existing listeners
    toggleBtn.onclick = null;
    
    toggleBtn.onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        
        console.log('🖱️ Button clicked! Current state:', isHidden ? 'hidden' : 'visible');
        
        isHidden = !isHidden;
        
        if (isHidden) {
            console.log('🙈 Hiding stations...');
            this.innerHTML = '<i class="fas fa-eye"></i> Show Stations';
            this.className = 'btn btn-sm btn-outline-success';
            stationsGrid.classList.add('d-none');
            if (stationCount) stationCount.classList.add('d-none');
        } else {
            console.log('👁️ Showing stations...');
            this.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Stations';
            this.className = 'btn btn-sm btn-outline-secondary';
            stationsGrid.classList.remove('d-none');
            if (stationCount) stationCount.classList.remove('d-none');
        }
        
        console.log('✅ Toggle complete! New state:', isHidden ? 'hidden' : 'visible');
    };
    
    // Mark as initialized
    toggleBtn.dataset.initialized = 'true';
    console.log('🎉 Stations collapse initialized successfully!');
    return true;
}

// Feedback functionality
function initializeFeedback() {
    const form = document.getElementById('feedbackForm');

    if (form) {
        form.addEventListener('submit', handleFeedbackSubmit);
    }
}

async function handleFeedbackSubmit(event) {
    event.preventDefault();

    const formData = {
        user_name: document.getElementById('feedbackName').value,
        user_email: document.getElementById('feedbackEmail').value,
        subject: document.getElementById('feedbackSubject').value,
        message: document.getElementById('feedbackMessage').value,
        feedback_type: document.getElementById('feedbackType').value
    };

    const statusDiv = document.getElementById('feedbackStatus');

    try {
        const response = await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        if (response.ok) {
            statusDiv.className = 'alert alert-success';
            statusDiv.textContent = 'Thank you for your feedback!';
            statusDiv.style.display = 'block';
            event.target.reset();
            setTimeout(() => { statusDiv.style.display = 'none'; }, 5000);
        } else {
            throw new Error('Failed to submit feedback');
        }
    } catch (error) {
        statusDiv.className = 'alert alert-danger';
        statusDiv.textContent = 'Error submitting feedback';
        statusDiv.style.display = 'block';
    }
}

// Data Filtering functionality
function initializeFiltering() {
    loadFilterOptions();
    const applyFilterBtn = document.getElementById('applyFilterBtn');
    const exportBtn = document.getElementById('exportBtn');
    const toggleMapBtn = document.getElementById('toggleMapBtn');

    if (applyFilterBtn) {
        applyFilterBtn.addEventListener('click', applyFilters);
    }

    if (exportBtn) {
        exportBtn.addEventListener('click', exportFilteredData);
    }
    
    if (toggleMapBtn) {
        toggleMapBtn.addEventListener('click', toggleMapVisualization);
    }
}



async function loadFilterOptions() {
    try {
        // Load locations from stations endpoint
        const stationsResp = await fetch(`${API_BASE}/bom/stations`);
        if (stationsResp.ok) {
            const stations = await stationsResp.json();
            const locations = [...new Set(stations.map(station => station.state))].sort();
            const locationSelect = document.getElementById('locationFilter');
            if (locationSelect) {
                locationSelect.innerHTML = '<option value="">All States</option>';
                locations.forEach(location => {
                    const option = document.createElement('option');
                    option.value = location;
                    option.textContent = location;
                    locationSelect.appendChild(option);
                });
            }
        }

        // Disable variables for now - use available data variables
        const variableSelect = document.getElementById('variableFilter');
        if (variableSelect) {
            variableSelect.innerHTML = '<option value="">All Variables</option>';
            const variables = ['Temperature', 'Rainfall', 'Evapotranspiration'];
            variables.forEach(variable => {
                const option = document.createElement('option');
                option.value = variable;
                option.textContent = variable.charAt(0).toUpperCase() + variable.slice(1);
                variableSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

async function applyFilters() {
    const location = document.getElementById('locationFilter').value;
    const variable = document.getElementById('variableFilter').value;
    const startDate = document.getElementById('startDateFilter').value;
    const endDate = document.getElementById('endDateFilter').value;

    const filteredResults = document.getElementById('filteredResults');
    const filterResultsContent = document.getElementById('filterResultsContent');
    const exportBtn = document.getElementById('exportBtn');

    // Show loading state
    filteredResults.style.display = 'block';
    filterResultsContent.innerHTML = '<div class="d-flex align-items-center"><div class="spinner-border spinner-border-sm me-2" role="status"></div>Loading filtered data...</div>';
    exportBtn.style.display = 'none';

    try {
        // Get stations data and filter client-side for now
        const response = await fetch(`${API_BASE}/bom/stations`);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const allStations = await response.json();
        
        // Filter stations based on selected criteria
        let filteredData = allStations;
        
        if (location) {
            filteredData = filteredData.filter(station => station.state === location);
        }
        
        // For now, just show station data - can be enhanced later
        // Convert station data to match expected format

        // Display results
        displayFilteredResults(filteredData);
        exportBtn.style.display = 'inline-block';
        
        // Update map visualization
        currentFilteredData = filteredData;
        updateMapWithFilteredData(filteredData, variable);
        
        // Show toggle map button if we have geolocated data
        const hasGeoData = filteredData.some(record => record.latitude && record.longitude);
        const toggleMapBtn = document.getElementById('toggleMapBtn');
        if (toggleMapBtn) {
            toggleMapBtn.style.display = hasGeoData ? 'inline-block' : 'none';
        }

    } catch (error) {
        console.error('Error applying filters:', error);
        filterResultsContent.innerHTML = `
            <div class="alert alert-danger">
                <h6><i class="fas fa-exclamation-circle"></i> Error Loading Filtered Data</h6>
                <p class="mb-0">${error.message}</p>
            </div>
        `;
        exportBtn.style.display = 'none';
    }
}

function displayFilteredResults(data) {
    const filterResultsContent = document.getElementById('filterResultsContent');

    if (!data || data.length === 0) {
        filterResultsContent.innerHTML = `
            <div class="alert alert-info">
                <i class="fas fa-info-circle"></i> No data found matching the selected filters.
            </div>
        `;
        return;
    }

    // Transform data from wide format to long format for display
    const transformedData = transformWideToLongFormat(data);

    // Create summary statistics
    const summary = calculateSummaryStats(transformedData);

    let html = `
        <div class="row mb-3">
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">${transformedData.length.toLocaleString()}</h5>
                        <p class="card-text text-muted">Total Records</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">${summary.uniqueLocations}</h5>
                        <p class="card-text text-muted">Locations</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">${summary.uniqueVariables}</h5>
                        <p class="card-text text-muted">Variables</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h5 class="card-title">${summary.dateRange}</h5>
                        <p class="card-text text-muted">Date Range</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="table-responsive">
            <table class="table table-striped table-hover">
                <thead class="table-dark">
                    <tr>
                        <th>Date</th>
                        <th>Location</th>
                        <th>Variable</th>
                        <th>Value</th>
                        <th>Unit</th>
                    </tr>
                </thead>
                <tbody>
    `;

    // Add data rows (limit to first 100 for performance)
    const displayData = transformedData.slice(0, 100);
    displayData.forEach(record => {
        html += `
            <tr>
                <td>${record.date || 'N/A'}</td>
                <td>${record.location || 'N/A'}</td>
                <td>${record.variable || 'N/A'}</td>
                <td>${record.value !== null && record.value !== undefined ? Number(record.value).toFixed(2) : 'N/A'}</td>
                <td>${record.unit || 'N/A'}</td>
            </tr>
        `;
    });

    html += `
                </tbody>
            </table>
        `;

    if (transformedData.length > 100) {
        html += `
            <div class="alert alert-info mt-3">
                <i class="fas fa-info-circle"></i> Showing first 100 records of ${transformedData.length.toLocaleString()} total results.
                Use the Export button to get all data.
            </div>
        `;
    }

    html += '</div>';

    filterResultsContent.innerHTML = html;

    // Store original data for export (not transformed)
    filterResultsContent.dataset.filteredData = JSON.stringify(data);
}

function transformWideToLongFormat(data) {
    const transformedData = [];
    
    // Define the weather variables and their units
    const variableMappings = {
        'evapotranspiration': { unit: 'mm', displayName: 'Evapotranspiration' },
        'rainfall': { unit: 'mm', displayName: 'Rainfall' },
        'max_temperature': { unit: '°C', displayName: 'Max Temperature' },
        'min_temperature': { unit: '°C', displayName: 'Min Temperature' },
        'max_humidity': { unit: '%', displayName: 'Max Humidity' },
        'min_humidity': { unit: '%', displayName: 'Min Humidity' },
        'wind_speed': { unit: 'km/h', displayName: 'Wind Speed' },
        'solar_radiation': { unit: 'MJ/m²', displayName: 'Solar Radiation' }
    };
    
    data.forEach(record => {
        // For each weather variable in the record
        Object.keys(variableMappings).forEach(variableKey => {
            if (record[variableKey] !== null && record[variableKey] !== undefined) {
                transformedData.push({
                    date: record.date,
                    location: record.location,
                    latitude: record.latitude,
                    longitude: record.longitude,
                    variable: variableMappings[variableKey].displayName,
                    value: record[variableKey],
                    unit: variableMappings[variableKey].unit
                });
            }
        });
    });
    
    return transformedData;
}

function calculateSummaryStats(data) {
    const locations = new Set();
    const variables = new Set();
    const dates = [];

    data.forEach(record => {
        if (record.location) locations.add(record.location);
        if (record.variable) variables.add(record.variable);
        if (record.date) dates.push(new Date(record.date));
    });

    const sortedDates = dates.sort((a, b) => a - b);
    const dateRange = sortedDates.length > 0 ?
        `${sortedDates[0].toLocaleDateString()} - ${sortedDates[sortedDates.length - 1].toLocaleDateString()}` :
        'N/A';

    return {
        uniqueLocations: locations.size,
        uniqueVariables: variables.size,
        dateRange: dateRange
    };
}

async function exportFilteredData() {
    const filterResultsContent = document.getElementById('filterResultsContent');
    const data = JSON.parse(filterResultsContent.dataset.filteredData || '[]');

    if (!data || data.length === 0) {
        alert('No data to export');
        return;
    }

    // Transform data to long format for export
    const transformedData = transformWideToLongFormat(data);

    // Convert to CSV
    const headers = ['Date', 'Location', 'Variable', 'Value', 'Unit'];
    const csvContent = [
        headers.join(','),
        ...transformedData.map(record => [
            record.date || '',
            record.location || '',
            record.variable || '',
            record.value || '',
            record.unit || ''
        ].map(field => `"${field}"`).join(','))
    ].join('\n');

    // Create and download file
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'filtered_weather_data.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

