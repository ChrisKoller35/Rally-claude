// RightSight Disabler - Ruft crop_assist_set_enabled(false) auf
// Kompiliert als 32-bit (x86) um die 32-bit DLL laden zu koennen
using System;
using System.Runtime.InteropServices;
using System.Text;

class RightSightDisabler
{
    // RightSightAPI.dll Funktionen
    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_init();

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_is_initialized();

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_get_devices(StringBuilder buffer, int bufferSize);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    static extern int crop_assist_is_enabled(string uuid, out bool enabled);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    static extern int crop_assist_set_enabled(string uuid, bool enabled);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    static extern int crop_assist_get_mode(string uuid, StringBuilder mode, int modeSize);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    static extern int crop_assist_set_mode(string uuid, string mode);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    static extern int crop_assist_get_device_info(string uuid, StringBuilder info, int infoSize);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_exit();

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    static extern int crop_assist_get_runtime_version(StringBuilder version, int versionSize);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetDllDirectory(string lpPathName);

    static void Main(string[] args)
    {
        string action = args.Length > 0 ? args[0].ToLower() : "status";
        string dllDir = @"C:\Program Files (x86)\Logitech\LogiSync\sync-agent\rightsight";
        
        Console.WriteLine("=== RightSight Controller ===");
        Console.WriteLine("Action: " + action);
        Console.WriteLine();

        // DLL-Suchpfad setzen
        SetDllDirectory(dllDir);

        try
        {
            // Init
            Console.WriteLine("Initialisiere RightSight API...");
            int initResult = crop_assist_init();
            Console.WriteLine("  crop_assist_init() = " + initResult);

            if (initResult != 0)
            {
                Console.WriteLine("FEHLER: Init fehlgeschlagen!");
                return;
            }

            // Version
            StringBuilder version = new StringBuilder(256);
            int verResult = crop_assist_get_runtime_version(version, 256);
            Console.WriteLine("  Version: " + version.ToString() + " (Result: " + verResult + ")");

            // Devices auflisten
            Console.WriteLine();
            Console.WriteLine("Suche Geraete...");
            StringBuilder devices = new StringBuilder(4096);
            int devResult = crop_assist_get_devices(devices, 4096);
            Console.WriteLine("  crop_assist_get_devices() = " + devResult);
            Console.WriteLine("  Devices: " + devices.ToString());

            // Fuer bekannte Kamera-UUID
            string uuid = "usb|vid=46d|pid=881|location=9335a81de00000";
            string serialNumber = "404ED540";
            
            // Versuche verschiedene UUID-Formate
            string[] uuids = new string[] {
                uuid,
                serialNumber,
                "usb|vid=46d|pid=881",
                "404ED540"
            };

            foreach (string testUuid in uuids)
            {
                Console.WriteLine();
                Console.WriteLine("--- Teste UUID: " + testUuid + " ---");
                
                // Device Info
                StringBuilder info = new StringBuilder(4096);
                int infoResult = crop_assist_get_device_info(testUuid, info, 4096);
                Console.WriteLine("  get_device_info = " + infoResult + ": " + info.ToString());

                // Enabled Status
                bool enabled = false;
                int enabledResult = crop_assist_is_enabled(testUuid, out enabled);
                Console.WriteLine("  is_enabled = " + enabledResult + ": " + enabled);

                // Mode
                StringBuilder mode = new StringBuilder(256);
                int modeResult = crop_assist_get_mode(testUuid, mode, 256);
                Console.WriteLine("  get_mode = " + modeResult + ": " + mode.ToString());

                if (enabledResult == 0 && action == "disable")
                {
                    Console.WriteLine();
                    Console.WriteLine("*** DEAKTIVIERE RIGHTSIGHT ***");
                    int setResult = crop_assist_set_enabled(testUuid, false);
                    Console.WriteLine("  crop_assist_set_enabled(false) = " + setResult);

                    // Verify
                    bool newEnabled = false;
                    crop_assist_is_enabled(testUuid, out newEnabled);
                    Console.WriteLine("  Neuer Status: Enabled = " + newEnabled);
                }
                else if (enabledResult == 0 && action == "enable")
                {
                    Console.WriteLine("*** AKTIVIERE RIGHTSIGHT ***");
                    int setResult = crop_assist_set_enabled(testUuid, true);
                    Console.WriteLine("  crop_assist_set_enabled(true) = " + setResult);
                }
            }

            // Cleanup
            Console.WriteLine();
            Console.WriteLine("Cleanup...");
            crop_assist_exit();
            Console.WriteLine("Fertig!");
        }
        catch (Exception ex)
        {
            Console.WriteLine("FEHLER: " + ex.Message);
            Console.WriteLine(ex.StackTrace);
        }
    }
}
