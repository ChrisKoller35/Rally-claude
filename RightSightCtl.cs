// RightSight Controller v2 - Korrigierte Signaturen
using System;
using System.Runtime.InteropServices;
using System.Text;

class RightSightCtl
{
    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_init();

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_exit();

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl)]
    static extern int crop_assist_is_initialized();

    // Versuche verschiedene Signaturen fuer is_enabled
    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_is_enabled", CharSet = CharSet.Ansi)]
    static extern int crop_assist_is_enabled_str(string uuid, out int enabled);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_is_enabled", CharSet = CharSet.Ansi)]
    static extern int crop_assist_is_enabled_bool(string uuid, out bool enabled);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_set_enabled", CharSet = CharSet.Ansi)]
    static extern int crop_assist_set_enabled_int(string uuid, int enabled);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_set_enabled", CharSet = CharSet.Ansi)]
    static extern int crop_assist_set_enabled_bool(string uuid, bool enabled);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_get_mode", CharSet = CharSet.Ansi)]
    static extern int crop_assist_get_mode(string uuid, StringBuilder mode, int size);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_set_mode", CharSet = CharSet.Ansi)]
    static extern int crop_assist_set_mode(string uuid, string mode);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_attach", CharSet = CharSet.Ansi)]
    static extern int crop_assist_attach(string uuid);

    [DllImport("RightSightAPI.dll", CallingConvention = CallingConvention.Cdecl, EntryPoint = "crop_assist_get_device_info", CharSet = CharSet.Ansi)]
    static extern int crop_assist_get_device_info_v1(string uuid, IntPtr info, int size);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetDllDirectory(string lpPathName);

    static void Main(string[] args)
    {
        string action = args.Length > 0 ? args[0].ToLower() : "status";
        string dllDir = @"C:\Program Files (x86)\Logitech\LogiSync\sync-agent\rightsight";
        
        Console.WriteLine("=== RightSight Controller v2 ===");
        Console.WriteLine("Action: " + action);
        
        SetDllDirectory(dllDir);

        try
        {
            // Init
            int initResult = crop_assist_init();
            Console.WriteLine("Init: " + initResult);
            
            if (initResult != 0)
            {
                Console.WriteLine("FEHLER: Init fehlgeschlagen!");
                return;
            }

            // Warte kurz bis Geraete erkannt werden
            System.Threading.Thread.Sleep(3000);
            Console.WriteLine("Geraete-Erkennung laeuft...");

            // Verschiedene UUID-Formate testen
            string[] uuids = new string[] {
                "404ED540",
                "usb|vid=46d|pid=881|location=9335a81de00000",
                "usb|vid=46d|pid=0881|location=9335a81de00000",
            };

            foreach (string uuid in uuids)
            {
                Console.WriteLine();
                Console.WriteLine("=== UUID: " + uuid + " ===");

                // is_enabled mit int
                try
                {
                    int enabledInt = 0;
                    int r1 = crop_assist_is_enabled_str(uuid, out enabledInt);
                    Console.WriteLine("  is_enabled(int): Result=" + r1 + " Enabled=" + enabledInt);
                }
                catch (Exception ex)
                {
                    Console.WriteLine("  is_enabled(int) FEHLER: " + ex.Message);
                }

                // is_enabled mit bool
                try
                {
                    bool enabledBool = false;
                    int r2 = crop_assist_is_enabled_bool(uuid, out enabledBool);
                    Console.WriteLine("  is_enabled(bool): Result=" + r2 + " Enabled=" + enabledBool);
                }
                catch (Exception ex)
                {
                    Console.WriteLine("  is_enabled(bool) FEHLER: " + ex.Message);
                }

                // get_mode
                try
                {
                    StringBuilder mode = new StringBuilder(256);
                    int r3 = crop_assist_get_mode(uuid, mode, 256);
                    Console.WriteLine("  get_mode: Result=" + r3 + " Mode=" + mode.ToString());
                }
                catch (Exception ex)
                {
                    Console.WriteLine("  get_mode FEHLER: " + ex.Message);
                }

                // DISABLE wenn action=disable
                if (action == "disable")
                {
                    Console.WriteLine();
                    Console.WriteLine("*** DEAKTIVIERE RIGHTSIGHT ***");
                    
                    try
                    {
                        int r4 = crop_assist_set_enabled_bool(uuid, false);
                        Console.WriteLine("  set_enabled(false): Result=" + r4);
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine("  set_enabled(bool,false) FEHLER: " + ex.Message);
                    }

                    try
                    {
                        int r5 = crop_assist_set_enabled_int(uuid, 0);
                        Console.WriteLine("  set_enabled(0): Result=" + r5);
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine("  set_enabled(int,0) FEHLER: " + ex.Message);
                    }

                    // Verify
                    try
                    {
                        int enabledAfter = 0;
                        int r6 = crop_assist_is_enabled_str(uuid, out enabledAfter);
                        Console.WriteLine("  VERIFY is_enabled: Result=" + r6 + " Enabled=" + enabledAfter);
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine("  VERIFY FEHLER: " + ex.Message);
                    }
                }
                
                if (action == "enable")
                {
                    Console.WriteLine("*** AKTIVIERE RIGHTSIGHT ***");
                    try
                    {
                        int r = crop_assist_set_enabled_bool(uuid, true);
                        Console.WriteLine("  set_enabled(true): Result=" + r);
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine("  FEHLER: " + ex.Message);
                    }
                }
            }

            // Cleanup
            crop_assist_exit();
            Console.WriteLine();
            Console.WriteLine("Fertig!");
        }
        catch (Exception ex)
        {
            Console.WriteLine("FEHLER: " + ex.Message);
            Console.WriteLine(ex.StackTrace);
        }
    }
}
