// Tab switching logic with localStorage
const tabButtons = document.querySelectorAll('.tab-button');
const tabContents = document.querySelectorAll('.tab-content');

// Function to show the active tab
function showTab(target) {
    // Hide all tabs and remove 'active' class from all buttons
    tabButtons.forEach(btn => btn.classList.remove('active'));
    tabContents.forEach(content => content.style.display = 'none');

    // Show the targeted tab and mark the button as active
    document.getElementById(target).style.display = 'block';
    document.querySelector(`.tab-button[data-target="${target}"]`).classList.add('active');
}

// Event listener for tab buttons
tabButtons.forEach(button => {
    button.addEventListener('click', () => {
        const target = button.getAttribute('data-target');
        // Save the active tab in localStorage
        localStorage.setItem('activeTab', target);
        // Show the selected tab
        showTab(target);

        // Force scroll to the bottom after switching to a tab
        if (target === 'MTBPanel') {
            scrollToBottom(logContainerMTB);
        } else if (target === 'MTdBPanel') {
            scrollToBottom(logContainerMTdB);
        }
    });
});

// On page load, check if there's an active tab stored in localStorage
document.addEventListener('DOMContentLoaded', () => {
    const activeTab = localStorage.getItem('activeTab') || 'homePanel'; // Default to homePanel if no tab is saved
    showTab(activeTab);

    // Scroll to the bottom of the log containers after a short delay to ensure they're fully rendered
    setTimeout(() => {
        scrollToBottom(logContainerMTB);  // Scroll the MTB log container
        scrollToBottom(logContainerMTdB); // Scroll the MTdB log container
    }, 100); // Delay of 100ms to ensure full rendering
});

// Functions to start, stop, and restart MTB
function startMTB() {
    console.log("Start MTB button clicked");
    fetch('/start_mtb', { method: 'POST' });
}

function stopMTB() {
    console.log("Stop MTB button clicked");
    fetch('/stop_mtb', { method: 'POST' });
}

function restartMTB() {
    console.log("Restart MTB button clicked");
    fetch('/restart_mtb', { method: 'POST' });
}

// Functions to start, stop, and restart MTdB
function startMTdB() {
    console.log("Start MTdB button clicked");
    fetch('/start_mtdb', { method: 'POST' });
}

function stopMTdB() {
    console.log("Stop MTdB button clicked");
    fetch('/stop_mtdb', { method: 'POST' });
}

function restartMTdB() {
    console.log("Restart MTdB button clicked");
    fetch('/restart_mtdb', { method: 'POST' });
}

// EventSource to stream logs from the MTB service
const evtSourceMTB = new EventSource('/logs/mtb');
const logOutputMTB = document.getElementById('logOutput');
const logContainerMTB = document.getElementById('logContainerMTB');

// Handle MTB log messages
evtSourceMTB.onmessage = function(event) {
    const logLine = document.createElement('div');
    logLine.textContent = event.data;
    logOutputMTB.appendChild(logLine);
    scrollToBottom(logContainerMTB);
};

// EventSource to stream logs from the MTdB service
const evtSourceMTdB = new EventSource('/logs/mtdb');
const logOutputMTdB = document.getElementById('logOutputMTdB');
const logContainerMTdB = document.getElementById('logContainerMTdB');

// Handle MTdB log messages
evtSourceMTdB.onmessage = function(event) {
    const logLine = document.createElement('div');
    logLine.textContent = event.data;
    logOutputMTdB.appendChild(logLine);
    scrollToBottom(logContainerMTdB);
};

// Function to scroll to the bottom of the log container
function scrollToBottom(container) {
    if (container) {
        container.scrollTop = container.scrollHeight;
    }
}

// Update the status indicator based on whether MTB is running
function updateMTBStatus() {
    const mtbSpinner = document.getElementById('mtbSpinner');
    mtbSpinner.style.display = 'inline-block'; // Show spinner while fetching status
    fetch('/mtb_status')
        .then(response => response.json())
        .then(data => {
            const statusLight = document.getElementById('statusLight');
            const statusText = document.getElementById('statusText');
            
            if (data.status === 'running') {
                statusLight.style.backgroundColor = 'green';
                statusText.textContent = 'Running';
            } else {
                statusLight.style.backgroundColor = 'red';
                statusText.textContent = 'Stopped';
            }
        })
        .finally(() => {
            mtbSpinner.style.display = 'none'; // Hide spinner after status is fetched
        })
        .catch(error => {
            console.error('Error fetching MTB status:', error);
        });
}

// Update the status indicator based on whether MTdB is running
function updateMTdBStatus() {
    const mtdbSpinner = document.getElementById('mtdbSpinner');
    mtdbSpinner.style.display = 'inline-block'; // Show spinner while fetching status
    fetch('/mtdb_status')
        .then(response => response.json())
        .then(data => {
            const statusLight = document.getElementById('mtdbStatusLight');
            const statusText = document.getElementById('mtdbStatusText');
            
            if (data.status === 'running') {
                statusLight.style.backgroundColor = 'green';
                statusText.textContent = 'Running';
            } else {
                statusLight.style.backgroundColor = 'red';
                statusText.textContent = 'Stopped';
            }
        })
        .finally(() => {
            mtdbSpinner.style.display = 'none'; // Hide spinner after status is fetched
        })
        .catch(error => {
            console.error('Error fetching MTdB status:', error);
        });
}

// Check MTB and MTdB statuses every 5 seconds
setInterval(updateMTBStatus, 5000);
setInterval(updateMTdBStatus, 5000);

// Also check statuses when the page loads
document.addEventListener('DOMContentLoaded', () => {
    updateMTBStatus();
    updateMTdBStatus();
});

const images = document.querySelectorAll('.image-container img');

// Track mouse movement across the entire page and apply 3D tilt effect
document.addEventListener('mousemove', (event) => {
    const windowWidth = window.innerWidth;
    const windowHeight = window.innerHeight;

    // Calculate mouse position relative to the center of the window
    const mouseX = (event.pageX - windowWidth / 2) / windowWidth * 50; // Adjust factor for tilt intensity
    const mouseY = (event.pageY - windowHeight / 2) / windowHeight * 50; // Adjust factor for tilt intensity

    // Apply 3D rotation based on mouse position
    images.forEach(image => {
        image.style.transform = `rotateY(${mouseX}deg) rotateX(${-mouseY}deg)`;
    });
});
