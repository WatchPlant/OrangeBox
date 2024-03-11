#include "led_driver.hpp"


// Define the file path for the named FIFO pipe
const std::string fifoFilePath = "/tmp/led_state";
std::ifstream fifoStream;


// Define the LED states
const int GPIO_PIN = 11;
ledTable  T[] =
//Pin  St Loop  State 0          State 1            State 2          State 3         Wkup
{ 
  { GPIO_PIN, 0, 0, {{MB_HIGH, 500, 0}, {MB_HIGH, 500, 0}, {MB_HIGH, 500, 0}, {MB_HIGH, 500, 0}}, 0},	// 0 - POWER ON
  { GPIO_PIN, 0, 0, {{MB_HIGH, 500, 0}, {MB_LOW, 500, 0}, {MB_HIGH, 500, 0}, {MB_LOW, 500, 0}}, 0},		// 1 - KERNEL LOADED
  { GPIO_PIN, 0, 0, {{MB_LOW, 200, 0}, {MB_HIGH, 100, 0}, {MB_LOOP, 0, 0}, {MB_HIGH, 1700, 0}}, 0 },	// 2 - LOADING-OFFLINE
  { GPIO_PIN, 0, 0, {{MB_LOW, 200, 0}, {MB_HIGH, 100, 0}, {MB_LOOP, 1, 0}, {MB_HIGH, 1400, 0}}, 0 },	// 3 - LOADING-ONLINE
  { GPIO_PIN, 0, 0, {{MB_HIGH, 100, 0}, {MB_LOW, 200, 0}, {MB_LOOP, 0, 0}, {MB_LOW, 1700, 0}}, 0 },		// 4 - READY-NO WIFI
  { GPIO_PIN, 0, 0, {{MB_HIGH, 100, 0}, {MB_LOW, 200, 0}, {MB_LOOP, 1, 0}, {MB_LOW, 1400, 0}}, 0 },		// 5 - READY-OFFLINE OPERATION
  { GPIO_PIN, 0, 0, {{MB_HIGH, 100, 0}, {MB_LOW, 200, 0}, {MB_LOOP, 2, 0}, {MB_LOW, 1100, 0}}, 0 },		// 6 - READY-ONLINE OPERATION
  { GPIO_PIN, 0, 0, {{MB_HIGH, 200, 0}, {MB_LOW, 200, 0}, {MB_HIGH, 200, 0}, {MB_LOW, 200, 0}}, 0},		// 7 - ERROR
};
const int NUM_STEPS = 4;  // Number steps of LED blinking loop
const int NUM_STATES = sizeof(T) / sizeof(T[0]);  // Number of states (different blinking modes)
volatile int STATE = 0;


// Function to continuously call control_led() with the value of STATE
void controlLED() {
	mraa::Result status;
	mraa::Gpio gpio_1(GPIO_PIN);
	/* set GPIO to output */
    status = gpio_1.dir(mraa::DIR_OUT);
    if (status != mraa::SUCCESS) {
        printError(status);
        return;
    }

	auto start = std::chrono::steady_clock::now();

	while (true) 
	{
		// check if the state active time has expired (ie, it is less than current time)
		if (millis(start).count() >= T[STATE].nextWakeup)
		{
			T[STATE].nextWakeup = millis(start).count() + T[STATE].state[T[STATE].currentState].activeTime;

			switch (T[STATE].state[T[STATE].currentState].activeVal)
			{
				case MB_LOW:
				case MB_HIGH:    // Write digital value
#ifdef TESTING
					consoleWrite(T[STATE].ledPin, T[STATE].state[T[STATE].currentState].activeVal == MB_HIGH ? 1 : 0);
#else
					status = gpio_1.write(T[STATE].state[T[STATE].currentState].activeVal == MB_HIGH ? 0 : 1);
					// if (status != mraa::SUCCESS) {
					// 	printError(status);
					// 	return EXIT_FAILURE;
					// }
#endif					
					T[STATE].currentState = (++T[STATE].currentState) % NUM_STEPS;
					break;
					
				case MB_LOOP:  // loop back to specified state if there is still count left
					// first time in this state set the loop counter
					if (T[STATE].currentLoop == LOOP_UNDEF)
					{
						T[STATE].currentLoop = T[STATE].state[T[STATE].currentState].activeTime;
					}

					// loop around or keep going?          
					if (T[STATE].currentLoop-- > 0)
					{
						T[STATE].currentState = T[STATE].state[T[STATE].currentState].nextState;
						T[STATE].nextWakeup = 0;  // do it immediately
					}
					else 
					{
						T[STATE].currentLoop = LOOP_UNDEF; // set up loop counter
						T[STATE].currentState = (++T[STATE].currentState) % NUM_STEPS;
					}
					break;  
					
				default:  // just move on - handles NULL and any stupid states we may get into
					T[STATE].currentState = (++T[STATE].currentState) % NUM_STEPS;
					break;
			}
		}

		// Sleep for a while (simulating the LED control operation)
		std::this_thread::sleep_for(
			std::chrono::duration_cast<std::chrono::nanoseconds>(
				std::chrono::duration<double>(0.01)));
	}
}

// Function to asynchronously check the named FIFO pipe and update STATE
void readFIFOPipe() {
	// Check if the named pipe exists
	if (access(fifoFilePath.c_str(), F_OK) == -1) {
		// Create the named pipe
		if (mkfifo(fifoFilePath.c_str(), 0666) == -1) {
			std::cerr << "Error creating named pipe." << std::endl;
			return;
		}
		std::cout << "Named pipe created successfully at " << fifoFilePath << std::endl;
	} else {
		std::cout << "Named pipe already exists at " << fifoFilePath << std::endl;
	}

	while (true) {
		// Open the named FIFO pipe for reading
		fifoStream.open(fifoFilePath);
		if (!fifoStream.is_open()) {
			std::cerr << "Error opening FIFO pipe for reading." << std::endl;
			return;
		}

		std::string line;
		// Read a line from the FIFO pipe
		getline(fifoStream, line);
		fifoStream.close();

		// Convert the read line to an integer and update STATE
		try {
			int newState = std::stoi(line);
			if (newState < 0 || newState >= NUM_STATES) {
				throw std::out_of_range("Value out of range");
			}
			STATE = newState;
			// std::cout << "STATE updated to: " << STATE << std::endl;
		} catch (const std::invalid_argument& e) {
			std::cerr << "Invalid data received from FIFO pipe: " << line << std::endl;
		} catch (const std::out_of_range& e) {
			std::cerr << "Value out of range: " << line << std::endl;
		}

		// Sleep for a while before checking the FIFO pipe again
		std::this_thread::sleep_for(std::chrono::seconds(1));
	}
}

// Signal handler for SIGINT
void sigintHandler(int signal) {
	std::cout << "Received SIGINT signal. Exiting..." << std::endl;
	exit(signal);
}

int main() {
	// Register the signal handler for SIGINT
	signal(SIGINT, sigintHandler);

	// Create two threads: one for controlling the LED and one for reading the FIFO pipe
	std::thread ledThread(controlLED);
	std::thread fifoThread(readFIFOPipe);

	// Wait for both threads to finish
	ledThread.join();
	fifoThread.join();

	return 0;
}
