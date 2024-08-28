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
    });
});

// On page load, check if there's an active tab stored in localStorage
document.addEventListener('DOMContentLoaded', () => {
    const activeTab = localStorage.getItem('activeTab') || 'homePanel'; // Default to homePanel if no tab is saved
    showTab(activeTab);
});

// Function to show a confirmation message
function showConfirmation(message, type = 'success') {
    const confirmationDiv = document.createElement('div');
    confirmationDiv.className = `confirmation-message ${type}`;
    confirmationDiv.textContent = message;
    
    // Append confirmation to the body or a specific container
    document.body.appendChild(confirmationDiv);
    
    // Automatically remove the message after 3 seconds
    setTimeout(() => {
        confirmationDiv.remove();
    }, 3000);
}

// Functions to start, stop, and restart MTB
function startMTB() {
    fetch('/start_mtb', { method: 'POST' })
        .then(response => {
            if (response.ok) {
                showConfirmation('MTB started successfully.');
            } else {
                showConfirmation('Failed to start MTB.', 'error');
            }
        })
        .catch(() => {
            showConfirmation('Failed to start MTB.', 'error');
        });
}

function stopMTB() {
    fetch('/stop_mtb', { method: 'POST' })
        .then(response => {
            if (response.ok) {
                showConfirmation('MTB stopped successfully.');
            } else {
                showConfirmation('Failed to stop MTB.', 'error');
            }
        })
        .catch(() => {
            showConfirmation('Failed to stop MTB.', 'error');
        });
}

function restartMTB() {
    fetch('/restart_mtb', { method: 'POST' })
        .then(response => {
            if (response.ok) {
                showConfirmation('MTB restarted successfully.');
            } else {
                showConfirmation('Failed to restart MTB.', 'error');
            }
        })
        .catch(() => {
            showConfirmation('Failed to restart MTB.', 'error');
        });
}

// Functions to start, stop, and restart MTdB
function startMTdB() {
    fetch('/start_mtdb', { method: 'POST' })
        .then(response => {
            if (response.ok) {
                showConfirmation('MTdB started successfully.');
            } else {
                showConfirmation('Failed to start MTdB.', 'error');
            }
        })
        .catch(() => {
            showConfirmation('Failed to start MTdB.', 'error');
        });
}

function stopMTdB() {
    fetch('/stop_mtdb', { method: 'POST' })
        .then(response => {
            if (response.ok) {
                showConfirmation('MTdB stopped successfully.');
            } else {
                showConfirmation('Failed to stop MTdB.', 'error');
            }
        })
        .catch(() => {
            showConfirmation('Failed to stop MTdB.', 'error');
        });
}

function restartMTdB() {
    fetch('/restart_mtdb', { method: 'POST' })
        .then(response => {
            if (response.ok) {
                showConfirmation('MTdB restarted successfully.');
            } else {
                showConfirmation('Failed to restart MTdB.', 'error');
            }
        })
        .catch(() => {
            showConfirmation('Failed to restart MTdB.', 'error');
        });
}

// Update the status indicator based on whether MTB is running
function updateMTBStatus() {
    fetch('/mtb_status')  // Assuming this is the correct Flask route
        .then(response => response.json())
        .then(data => {
            const statusLight = document.getElementById('statusLight');
            const statusText = document.getElementById('statusText');
            
            if (data.status === 'running') {
                statusLight.style.backgroundColor = 'green';  // Set background color to green
                statusLight.classList.add('glow');  // Add glowing effect when running
                statusText.textContent = 'Running';
            } else {
                statusLight.style.backgroundColor = 'red';  // Set background color to red
                statusLight.classList.remove('glow');  // Remove glowing effect when stopped
                statusText.textContent = 'Stopped';
            }
        })
        .catch(error => {
            console.error('Error fetching MTB status:', error);
        });
}

// Update the status indicator based on whether MTdB is running
function updateMTdBStatus() {
    fetch('/mtdb_status')  // Assuming this is the correct Flask route
        .then(response => response.json())
        .then(data => {
            const mtdbStatusLight = document.getElementById('mtdbStatusLight');
            const mtdbStatusText = document.getElementById('mtdbStatusText');
            
            if (data.status === 'running') {
                mtdbStatusLight.style.backgroundColor = 'green';  // Set background color to green
                mtdbStatusLight.classList.add('glow');  // Add glowing effect when running
                mtdbStatusText.textContent = 'Running';
            } else {
                mtdbStatusLight.style.backgroundColor = 'red';  // Set background color to red
                mtdbStatusLight.classList.remove('glow');  // Remove glowing effect when stopped
                mtdbStatusText.textContent = 'Stopped';
            }
        })
        .catch(error => {
            console.error('Error fetching MTdB status:', error);
        });
}

// Check the statuses when the page loads
document.addEventListener('DOMContentLoaded', () => {
    updateMTBStatus();
    updateMTdBStatus();

    // Optionally, update statuses periodically (e.g., every 5 seconds)
    setInterval(updateMTBStatus, 5000);
    setInterval(updateMTdBStatus, 5000);
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

// Function to show or hide the spinner using display property
function toggleSpinner(visible) {
    const spinner = document.getElementById('statisticsSpinner');
    if (spinner) {
        spinner.style.display = visible ? 'block' : 'none';  // Toggle visibility
    }
}

// Function to format post hash
function formatPostHash(hash) {
    return hash.slice(0, 7) + "..." + hash.slice(-7); // Shorten hash display
}

// Function to copy text to the clipboard using the Clipboard API
function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        // Use Clipboard API if available
        navigator.clipboard.writeText(text)
            .then(() => {
                showConfirmation('Copied to clipboard!');
            })
            .catch(err => {
                console.error('Error copying to clipboard:', err);
                showConfirmation('Failed to copy to clipboard', 'error');
            });
    } else {
        // Fallback method using a temporary input if Clipboard API is not available
        const tempInput = document.createElement('input');
        tempInput.value = text;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand('copy');
        document.body.removeChild(tempInput);
        showConfirmation('Copied to clipboard (fallback method).');
    }
}

// Function to update the transaction table and add click-to-copy functionality
function updateTransactionTable(transactions) {
    const tableBody = document.querySelector('#transactionTable tbody');
    tableBody.innerHTML = '';  // Clear the table first

    transactions.forEach(transaction => {
        const row = document.createElement('tr');

        const buyStatusClass = transaction.buy === 'YES' ? 'status-yes' : 'status-no';
        const sellStatusClass = transaction.sell === 'YES' ? 'status-yes' : 'status-no';
        const profitLossClass = transaction.profit_loss > 0 ? 'profit' : 'loss';

        // Add clickable elements for post_hash, buy_tx, and sell_tx
        row.innerHTML = `
            <td>${new Date(transaction.time).toLocaleString()}</td> <!-- Time column -->
            <td class="short-hash" onclick="copyToClipboard('${transaction.post_hash}')">${formatPostHash(transaction.post_hash)}</td> <!-- Post hash copies -->
            <td>${transaction.wallet_name}</td>
            <td class="token-symbol" onclick="copyToClipboard('${transaction.token_hash}')">${transaction.token_symbol}</td> <!-- Token symbol copies token_hash -->
            <td>${transaction.amount_of_eth}</td>
            
            <!-- Buy column: only clickable if buy_tx exists -->
            <td class="buy-tx ${buyStatusClass}" ${transaction.buy_tx ? `onclick="copyToClipboard('${transaction.buy_tx}')"` : ''}>
                ${transaction.buy || ''}
            </td>
            
            <!-- Sell column: only clickable if sell_tx exists -->
            <td class="sell-tx ${sellStatusClass}" ${transaction.sell_tx ? `onclick="copyToClipboard('${transaction.sell_tx}')"` : ''}>
                ${transaction.sell || ''}
            </td>

            <td>${transaction.fail || ''}</td>
            <td class="${profitLossClass}">${transaction.profit_loss || ''}</td>
        `;

        tableBody.appendChild(row);
    });
}

// Function to fetch the transaction logs and display the spinner while loading
function fetchTransactionLogs() {
    toggleSpinner(true); // Show spinner before fetching data
    fetch('/get_transactions')
        .then(response => response.json())
        .then(data => {
            if (!data.error) {
                updateTransactionTable(data);
            }
        })
        .finally(() => {
            toggleSpinner(false); // Hide spinner after data is loaded
        })
        .catch(error => {
            console.error('Error fetching transactions:', error);
            toggleSpinner(false); // Hide spinner even on error
        });
}

// Poll the server every 5 seconds for new transaction logs
setInterval(fetchTransactionLogs, 5000);

// Fetch the transaction logs when the page loads
document.addEventListener('DOMContentLoaded', () => {
    fetchTransactionLogs();
});