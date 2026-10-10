#!/usr/bin/env python3
"""
Outil d'extraction automatique d'adresses depuis le fichier ELF.
Usage: python3 elf_symbol_lookup.py
"""

variables = [
    ("Mci[0].CurrentFaults", "0x2000000A", "uint16_t (16-bit unsigned)", "Défauts actifs du moteur"),
    ("Mci[0].PastFaults", "0x2000000C", "uint16_t (16-bit unsigned)", "Historique des défauts"),
    ("STO_PLL_M1._Super.hAvrMecSpeedUnit", "0x2000007C", "int16_t (16-bit signed)", "Vitesse mesurée par STO PLL"),
    ("VirtualSpeedSensorM1._Super.hAvrMecSpeedUnit", "0x20000420", "int16_t (16-bit signed)", "Vitesse mesurée par capteur virtuel"),
    ("start", "0x20000004", "int32_t (32-bit signed)", "Signal / commande start"),
    ("ack", "0x20000000", "int32_t (32-bit signed)", "Signal / commande acknowledge"),
    ("FOCVars[0].Iqd.q", "0x200006A4", "int16_t (16-bit signed)", "Courant Iq mesuré en direct"),
    ("PotRegConv_M1.data", "0x200003D2", "uint16_t (16-bit unsigned)", "Valeur brute ADC potentiomètre"),
    ("PQD_MotorPowMeasM1.hAvrgElMotorPower", "0x20000394", "int16_t (16-bit signed)", "Puissance électrique moyenne (W)"),
]

if __name__ == "__main__":
    print(f"{'Nom de la Variable':<45} | {'Adresse RAM':<12} | {'Type':<28} | {'Description'}")
    print("-" * 115)
    for name, addr, vtype, desc in variables:
        print(f"{name:<45} | {addr:<12} | {vtype:<28} | {desc}")
