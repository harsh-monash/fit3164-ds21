/* ================================================
   Weather Station Map - Leaflet.js Implementation
   ================================================ */

let stationMap = null;
let markersLayer = null;
let allStationsData = [];

// Temperature color mapping
function getTemperatureColor(temp) {
    if (temp === null || temp === undefined) return '#6b7280'; // Gray for no data
    if (temp < 15) return '#3b82f6'; // Blue - Cold
    if (temp < 25) return '#10b981'; // Green - Mild
    if (temp < 35) return '#f59e0b'; // Orange - Warm
    return '#ef4444'; // Red - Hot
}

// Initialize map when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('stationMap')) {
        initializeMap();
    }
});

// Initialize Leaflet map
async function initializeMap() {
    try {
        // Show loading state
        showMapLoading(true);
        
        // Initialize map centered on Australia
        stationMap = L.map('stationMap', {
            center: [-25.2744, 133.7751], // Center of Australia
            zoom: 5,
            minZoom: 4,
            maxZoom: 18,
            zoomControl: true
        });
        
        // Add tile layer - Using standard OpenStreetMap for reliability
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            maxZoom: 19
        }).addTo(stationMap);
        
        // Create marker cluster group
        markersLayer = L.markerClusterGroup({
            maxClusterRadius: 50,
            spiderfyOnMaxZoom: true,
            showCoverageOnHover: false,
            zoomToBoundsOnClick: true,
            chunkedLoading: true,
            iconCreateFunction: function(cluster) {
                const childCount = cluster.getChildCount();
                let size = 'small';
                if (childCount > 100) size = 'large';
                else if (childCount > 50) size = 'medium';
                
                return L.divIcon({
                    html: '<div><span>' + childCount + '</span></div>',
                    className: 'marker-cluster marker-cluster-' + size,
                    iconSize: L.point(40, 40)
                });
            }
        });
        
        // Fetch and display stations
        await loadStations();
        
        // Setup map controls
        setupMapControls();
        
        // Integrate with search box
        integrateWithSearch();
        
        // Hide loading state
        showMapLoading(false);
        
    } catch (error) {
        console.error('Error initializing map:', error);
        showMapLoading(false);
        alert('Error loading map. Please refresh the page.');
    }
}

// Fetch station data from API
async function loadStations() {
    try {
        const response = await fetch('/api/bom/stations');
        if (!response.ok) {
            throw new Error('Failed to fetch stations');
        }
        
        const stations = await response.json();
        allStationsData = stations;
        
        console.log(`Loaded ${stations.length} stations`);
        
        // Update stats
        updateMapStats(stations);
        
        // Create markers for all stations
        createMarkers(stations);
        
    } catch (error) {
        console.error('Error loading stations:', error);
        throw error;
    }
}

// Create markers for stations
function createMarkers(stations) {
    // Clear existing markers
    if (markersLayer) {
        markersLayer.clearLayers();
    }
    
    let validStations = 0;
    
    stations.forEach(station => {
        // Check if station has valid coordinates
        if (!station.latitude || !station.longitude) {
            return;
        }
        
        validStations++;
        
        // Get temperature for color coding (use average max temp or random for demo)
        const temperature = station.avg_max_temp || null;
        const color = getTemperatureColor(temperature);
        
        // Create custom marker icon
        const markerIcon = L.divIcon({
            className: 'custom-marker',
            html: `<div style="
                background-color: ${color};
                width: 24px;
                height: 24px;
                border-radius: 50%;
                border: 3px solid white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.5);
            "></div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
            popupAnchor: [0, -12]
        });
        
        // Create marker
        const marker = L.marker([station.latitude, station.longitude], {
            icon: markerIcon,
            title: station.station_name
        });
        
        // Create popup content
        const popupContent = createPopupContent(station, temperature);
        marker.bindPopup(popupContent, {
            maxWidth: 300,
            className: 'station-popup-wrapper'
        });
        
        // Add marker to cluster group
        markersLayer.addLayer(marker);
    });
    
    // Add marker cluster group to map
    stationMap.addLayer(markersLayer);
    
    console.log(`Created ${validStations} markers`);
    
    // Update visible stations count
    updateVisibleStations();
    
    // Listen for map move to update visible count
    stationMap.on('moveend', updateVisibleStations);
}

// Create popup content for a station
function createPopupContent(station, temperature) {
    const tempDisplay = temperature !== null ? 
        `${temperature.toFixed(1)}°C` : 
        '<span style="color: #6b7280;">No data</span>';
    
    const stateDisplay = station.state || 'Unknown';
    const elevationDisplay = station.elevation ? 
        `${station.elevation}m` : 
        'Unknown';
    
    return `
        <div class="station-popup">
            <div class="station-popup-header">
                <i class="fas fa-cloud-sun"></i>
                ${station.station_name}
            </div>
            <div class="station-popup-info">
                <div class="station-info-row">
                    <i class="fas fa-thermometer-half"></i>
                    <span class="station-info-label">Avg Temp:</span>
                    <span class="station-info-value">${tempDisplay}</span>
                </div>
                <div class="station-info-row">
                    <i class="fas fa-map-marker-alt"></i>
                    <span class="station-info-label">State:</span>
                    <span class="station-info-value">${stateDisplay}</span>
                </div>
                <div class="station-info-row">
                    <i class="fas fa-mountain"></i>
                    <span class="station-info-label">Elevation:</span>
                    <span class="station-info-value">${elevationDisplay}</span>
                </div>
                <div class="station-info-row">
                    <i class="fas fa-${station.is_active ? 'check-circle' : 'times-circle'}"></i>
                    <span class="station-info-label">Status:</span>
                    <span class="station-info-value">${station.is_active ? 'Active' : 'Inactive'}</span>
                </div>
            </div>
            <a href="/analysis?station=${encodeURIComponent(station.station_name)}" 
               class="station-popup-btn">
                <i class="fas fa-chart-line"></i>
                View Full Analysis
            </a>
        </div>
    `;
}

// Setup map control buttons
function setupMapControls() {
    // Locate button - find user's location
    const locateBtn = document.getElementById('locateBtn');
    if (locateBtn) {
        locateBtn.addEventListener('click', function() {
            if (!navigator.geolocation) {
                alert('Geolocation is not supported by your browser');
                return;
            }
            
            locateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    // Fly to user's location
                    stationMap.flyTo([lat, lon], 10, {
                        duration: 1.5
                    });
                    
                    // Add temporary marker
                    const userMarker = L.marker([lat, lon], {
                        icon: L.divIcon({
                            className: 'user-location-marker',
                            html: '<div style="background: #00d4ff; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(0,212,255,0.8);"></div>',
                            iconSize: [16, 16],
                            iconAnchor: [8, 8]
                        })
                    }).addTo(stationMap);
                    
                    // Remove marker after 5 seconds
                    setTimeout(() => userMarker.remove(), 5000);
                    
                    locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i>';
                },
                function(error) {
                    console.error('Geolocation error:', error);
                    alert('Unable to get your location. Please check browser permissions.');
                    locateBtn.innerHTML = '<i class="fas fa-location-arrow"></i>';
                }
            );
        });
    }
    
    // Reset view button
    const resetViewBtn = document.getElementById('resetViewBtn');
    if (resetViewBtn) {
        resetViewBtn.addEventListener('click', function() {
            stationMap.flyTo([-25.2744, 133.7751], 5, {
                duration: 1.5
            });
        });
    }
}

// Integrate map with search box
function integrateWithSearch() {
    // Listen for search results
    const searchResultsContent = document.getElementById('topPlaceSearchResults');
    if (searchResultsContent) {
        searchResultsContent.addEventListener('click', function(e) {
            const item = e.target.closest('.list-group-item');
            if (item && item.dataset.lat && item.dataset.lon) {
                const lat = parseFloat(item.dataset.lat);
                const lon = parseFloat(item.dataset.lon);
                
                // Fly to location on map
                if (stationMap) {
                    stationMap.flyTo([lat, lon], 10, {
                        duration: 1.5
                    });
                    
                    // Scroll to map section
                    const mapSection = document.querySelector('.map-section');
                    if (mapSection) {
                        mapSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }
            }
        });
    }
}

// Update map statistics
function updateMapStats(stations) {
    const totalStations = stations.length;
    const activeStations = stations.filter(s => s.is_active).length;
    
    document.getElementById('totalStations').textContent = totalStations;
    document.getElementById('activeStations').textContent = activeStations;
}

// Update visible stations count
function updateVisibleStations() {
    if (!stationMap || !markersLayer) return;
    
    const bounds = stationMap.getBounds();
    let visibleCount = 0;
    
    markersLayer.eachLayer(function(layer) {
        if (layer instanceof L.Marker) {
            if (bounds.contains(layer.getLatLng())) {
                visibleCount++;
            }
        }
    });
    
    document.getElementById('visibleStations').textContent = visibleCount;
}

// Show/hide map loading state
function showMapLoading(show) {
    const loadingEl = document.getElementById('mapLoading');
    if (loadingEl) {
        if (show) {
            loadingEl.classList.remove('hidden');
        } else {
            loadingEl.classList.add('hidden');
        }
    }
}

// Expose functions for external use
window.mapFunctions = {
    panToLocation: function(lat, lon, zoom = 10) {
        if (stationMap) {
            stationMap.flyTo([lat, lon], zoom, { duration: 1.5 });
        }
    },
    findNearestStation: function(lat, lon) {
        if (!allStationsData.length) return null;
        
        let nearest = null;
        let minDistance = Infinity;
        
        allStationsData.forEach(station => {
            if (station.latitude && station.longitude) {
                const distance = Math.sqrt(
                    Math.pow(station.latitude - lat, 2) + 
                    Math.pow(station.longitude - lon, 2)
                );
                
                if (distance < minDistance) {
                    minDistance = distance;
                    nearest = station;
                }
            }
        });
        
        return nearest;
    }
};
