from opentrons import protocol_api

# 1. Metadata: Helps the app identify the protocol
metadata = {
    'protocolName': 'Dummy Reagent Transfer',
    'author': 'Lach',
    'description': 'A simple script to transfer liquid from a reservoir to a 96-well plate.',
    'apiLevel': '2.28'
}

def run(protocol: protocol_api.ProtocolContext):

    # 2. Load Labware
    # Tips: Opentrons 300ul tips on slot 1
    tips = protocol.load_labware('opentrons_96_tiprack_300ul', '1')

    # Reservoir: 12-well reagent reservoir on slot 2
    reservoir = protocol.load_labware('nest_12_reservoir_15ml', '2')

    # Plate: NEST 96-well plate on slot 3
    plate = protocol.load_labware('greiner_96_wellplate_323ul', '3')

    # 3. Load Pipette
    # Using a Single-channel P300 pipette on the right mount
    left_pipette = protocol.load_instrument('p300_single_gen2', 'left', tip_racks=[tips])

    # 4. Command Logic
    # We will pull 100ul from the first well of the reservoir 
    # and distribute it to the first 8 wells of the plate.
    
    reagent_source = reservoir.wells_by_name()['A1']
    target_wells = plate.wells()[:8]

    # Start the liquid handling
    left_pipette.pick_up_tip()

    for well in target_wells:
        left_pipette.aspirate(100, reagent_source)
        left_pipette.dispense(100, well)
        left_pipette.touch_tip() # Optional: cleans the drop off the side

    left_pipette.drop_tip()
    
    protocol.comment("Protocol complete! All wells filled.")