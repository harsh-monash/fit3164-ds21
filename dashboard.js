// Minimal dashboard bootstrap: fetch statistics and stations and populate the page
const API_BASE = '/api/v1';
let weatherMap = null;
let markersLayer = null;

// Global error handler
window.addEventListener('error', function(e) {
    console.error('JavaScript error:', e.error);
});

document.addEventListener('DOMContentLoaded', () => {
    loadStatistics();
    loadStations();
    initializeMap();
    initializeSearch();
    initializeFeedback();
});

function initializeMap() {
	// Initialize the Leaflet map centered on NSW, Australia
	weatherMap = L.map('weatherMap').setView([-32.0, 147.0], 6);
	
	// Add OpenStreetMap tiles
	L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		attribution: '© OpenStreetMap contributors'
	}).addTo(weatherMap);
	
	// Create a layer group for markers
	markersLayer = L.layerGroup().addTo(weatherMap);
	
	// Load stations on map
	loadStationsOnMap();
}

async function loadStationsOnMap() {
	try {
		// Clear existing markers
		if (markersLayer) {
			markersLayer.clearLayers();
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
				markersLayer.addLayer(marker);
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
			return;
		}
		
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
		
		// Display results
		searchResults.innerHTML = results.map(result => `
			<button class="list-group-item list-group-item-action" data-lat="${result.lat}" data-lon="${result.lon}" data-name="${result.display_name}">
				<div class="fw-bold">${result.name || result.display_name}</div>
				<small class="text-muted">${result.display_name}</small>
			</button>
		`).join('');
		
		// Add click handlers to result items
		searchResults.querySelectorAll('.list-group-item').forEach(item => {
			item.addEventListener('click', () => {
				const lat = parseFloat(item.dataset.lat);
				const lon = parseFloat(item.dataset.lon);
				const name = item.dataset.name;
				
				selectLocation(lat, lon, name);
				searchResults.innerHTML = '';
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
		
		let resultHtml = `
			<div class="row mb-3">
				<div class="col-12">
					<p class="mb-1"><strong>Coordinates:</strong> ${lat.toFixed(4)}, ${lon.toFixed(4)}</p>
				</div>
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
		console.log(resp)
        if (!resp.ok) throw new Error('Failed to load statistics');
        const data = await resp.json();
        // BOM API returns { dataset_overview: {total_records, total_stations}, temperature: {min_average, max_average}, evapotranspiration: {average} }
        const totalRecords = data.dataset_overview?.total_records ?? 0;
        const totalStations = data.dataset_overview?.total_stations ?? 0;
        const avgTemp = data.temperature?.min_average ?? data.temperature?.max_average ?? null;
        const avgET = data.evapotranspiration?.average ?? null;
        
        document.getElementById('totalRecords').textContent = Number(totalRecords).toLocaleString();
        document.getElementById('totalStations').textContent = totalStations;
        document.getElementById('avgTemp').textContent = avgTemp !== null ? `${Number(avgTemp).toFixed(1)}°C` : 'N/A';
        document.getElementById('avgET').textContent = avgET !== null ? `${Number(avgET).toFixed(2)} mm` : 'N/A';
        
    } catch (err) {
        console.error('Statistics load error', err);
        document.getElementById('totalRecords').textContent = 'Error';
        document.getElementById('totalStations').textContent = 'Error';
        document.getElementById('avgTemp').textContent = 'Error';
        document.getElementById('avgET').textContent = 'Error';
    }
}

async function loadStations() {
	try {
		const resp = await fetch(`${API_BASE}/bom/stations`);
		if (!resp.ok) throw new Error('Failed to load stations');
		const stations = await resp.json();
		document.getElementById('stationCount').textContent = `${stations.length} stations`;
		const grid = document.getElementById('stationsGrid');
		grid.innerHTML = stations.map(s => {
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
	} catch (err) {
		console.error('Stations load error', err);
		document.getElementById('stationCount').textContent = 'Error loading stations';
	}
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

// === Layer containers ===
const layers = {
  temperature: L.layerGroup(),
  humidity: L.layerGroup(),
  wind: L.layerGroup(),
  pressure: L.layerGroup(),
  hotWet: L.layerGroup(),
  hotDry: L.layerGroup(),
};

const areaLayers = {
  hotWetArea: L.layerGroup(),
  hotDryArea: L.layerGroup(),
  otherArea: L.layerGroup(),
};

function colorRampTemp(t) {
  if (t == null) return '#999';
  if (t < 10) return '#4575b4';
  if (t < 20) return '#91bfdb';
  if (t < 30) return '#fee090';
  return '#d73027';
}

function colorRampHumidity(h) {
  if (h == null) return '#999';
  if (h < 30) return '#fddbc7';
  if (h < 60) return '#f4a582';
  if (h < 80) return '#92c5de';
  return '#2166ac';
}

function pressureStroke(p) {
  if (p == null) return '#999';
  if (p < 1000) return '#bbb';
  if (p < 1015) return '#888';
  return '#333';
}

function fillForClass(c) {
  switch (c) {
    case 'hot_wet': return '#6a3d9a';
    case 'hot_dry': return '#e31a1c';
    default: return '#bdbdbd';
  }
}

// Backend data
async function fetchStationsLatest() {
  const url = `/api/v1/stations/latest-geojson?hot_threshold=30&wet_threshold=70`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Fetch failed: ${res.status}`);
  return res.json();
}

async function fetchGrid(cellKm = 50) {
  const res = await fetch(`/api/v1/stations/grid-classes?cell_km=${cellKm}&hot_threshold=30&wet_threshold=70`);
  if (!res.ok) throw new Error(`Grid fetch failed: ${res.status}`);
  return res.json();
}

// Renderers
function addStationLayers(featureCollection) {
  Object.values(layers).forEach(l => l.clearLayers());

  featureCollection.features.forEach(f => {
    if (!f.geometry) return;
    const p = f.properties || {};
    const [lng, lat] = f.geometry.coordinates;

    const tempMarker = L.circleMarker([lat, lng], {
      radius: 6, color: colorRampTemp(p.temperature), weight: 2, fillOpacity: 0.7
    }).bindTooltip(`${p.name || 'Station'}<br>Temp: ${p.temperature ?? '–'}°C`);
    tempMarker.addTo(layers.temperature);

    const humMarker = L.circleMarker([lat, lng], {
      radius: 6, color: colorRampHumidity(p.humidity), weight: 2, fillOpacity: 0.7
    }).bindTooltip(`${p.name || 'Station'}<br>RH: ${p.humidity ?? '–'}%`);
    humMarker.addTo(layers.humidity);

    if (p.wind_speed != null) {
      const dx = 0.02 * (p.wind_speed / 10);
      const windLine = L.polyline([[lat, lng], [lat, lng + dx]], { weight: 2, opacity: 0.9 })
        .bindTooltip(`${p.name || 'Station'}<br>Wind: ${p.wind_speed} m/s`);
      windLine.addTo(layers.wind);
    }

    const pressMarker = L.circle([lat, lng], {
      radius: 500, color: pressureStroke(p.pressure), weight: 1, fill: false
    }).bindTooltip(`${p.name || 'Station'}<br>Pressure: ${p.pressure ?? '–'} hPa`);
    pressMarker.addTo(layers.pressure);

    if (p.is_hot && p.is_wet) {
      L.circleMarker([lat, lng], { radius: 7, color: '#6a3d9a', weight: 3, fillOpacity: 0.8 })
        .bindTooltip(`${p.name || 'Station'}<br><b>Hot & Wet</b>`)
        .addTo(layers.hotWet);
    } else if (p.is_hot && p.is_wet === false) {
      L.circleMarker([lat, lng], { radius: 7, color: '#e31a1c', weight: 3, fillOpacity: 0.8 })
        .bindTooltip(`${p.name || 'Station'}<br><b>Hot & Dry</b>`)
        .addTo(layers.hotDry);
    }
  });
}

function addAreaLayers(featureCollection) {
  Object.values(areaLayers).forEach(l => l.clearLayers());

  featureCollection.features.forEach(f => {
    const klass = f.properties?.class || 'other';
    const poly = L.geoJSON(f, {
      style: { color: '#333', weight: 1, fillColor: fillForClass(klass), fillOpacity: (klass === 'other' ? 0.15 : 0.35) }
    }).bindTooltip(
      `Class: ${klass}<br>` +
      `Mean Temp: ${f.properties?.mean_temp?.toFixed?.(1) ?? '–'}°C<br>` +
      `Mean RH: ${f.properties?.mean_rh?.toFixed?.(0) ?? '–'}%<br>` +
      `Stations: ${f.properties?.station_count ?? 0}`
    );

    if (klass === 'hot_wet') poly.addTo(areaLayers.hotWetArea);
    else if (klass === 'hot_dry') poly.addTo(areaLayers.hotDryArea);
    else poly.addTo(areaLayers.otherArea);
  });
}

// Merge with your existing initializeMap() flow:
async function initializeMap() {
  // If already initialised, do nothing
  if (window.__mapInitialised) return;
  window.__mapInitialised = true;

  // Use the SAME element id as your HTML (weatherMap)
  weatherMap = L.map('weatherMap').setView([-32.0, 147.0], 6);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(weatherMap);

  // Build our layers
  const stationFC = await fetchStationsLatest();
  addStationLayers(stationFC);

  const gridFC = await fetchGrid(50);
  addAreaLayers(gridFC);

  // Add to map (default on)
  Object.values(layers).forEach(l => l.addTo(weatherMap));
  Object.values(areaLayers).forEach(l => l.addTo(weatherMap));

  // Layer control
  const overlayPoints = {
    "Temperature (pts)": layers.temperature,
    "Humidity (pts)": layers.humidity,
    "Wind (barbs)": layers.wind,
    "Pressure (rings)": layers.pressure,
    "Hot & Wet (pts)": layers.hotWet,
    "Hot & Dry (pts)": layers.hotDry,
  };
  const overlayAreas = {
    "AREA: Hot & Wet": areaLayers.hotWetArea,
    "AREA: Hot & Dry": areaLayers.hotDryArea,
    "AREA: Other": areaLayers.otherArea,
  };
  L.control.layers({}, { ...overlayAreas, ...overlayPoints }, { collapsed: false }).addTo(weatherMap);

  
}

