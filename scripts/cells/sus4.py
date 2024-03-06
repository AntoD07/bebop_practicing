dominant_essential_starting_cells = {
    1: {
        "Descending Bebop scale from root": ["1", "maj7", "7", "6", "5"],
        "Coltrane Pattern from root": ["1", "9", "3", "5", "7"],
        "Lee Morgan Dominant": ["1", "maj7", "7", "9", "6"],
        "Minor Honeysuckle Rose": ["1", "7", "9", "4", "6"],
        "Jimmy Heath": ["1", "maj7", "7", "9", "4"],
    },
    3: {
        "Dominant Bebop Scale from 3rd": ["3", "9", "1", "maj7", "7"],
        "Dominant 9th Arpeggio": ["3", "5", "7", "9", "1"],
        "Dexter Gordon": ["3", "4", "9", "7", "6"],
        "Descending Dominant Scale from 3rd": ["3", "9", "1", "7", "6"],
    },
    5: {
        "Ascending II Scale": ["5", "6", "7", "1", "9"],
        "Descending Dominant Scale from 5th": ["5", "4", "3", "2", "1"],
        "Ascending II-Minor 7th Arpeggio (ending on 3rd)": ["5", "7", "9", "4", "3"],
        "Ascending II-Minor 7th Arpeggio (ending on 6th)": ["5", "7", "9", "4", "6"],
        "Diatonic Enclosure of 3rd": ["5", "9", "4", "9", "3"],
        "Diatonic Enclosure to #11": ["5", "9", "4", "9", "#11"],
        "Cannonball Adderley Approach": ["5", "4", "3", "4", "9"],
    },
    7: {
        "Descending Dominant Scale from 7th ending on 3rd": ["7", "6", "5", "4", "3"],
        "Coltrane Pattern from 7th (ending on 3rd)": ["7", "1", "9", "4", "3"],
        "Hank Mobley": ["7", "2", "6", "5", "1"],
        "Stan Getz enclosure of II Root": ["7", "4", "#11", "6", "5"],
        "Ascending Scale from 7th": ["7", "1", "9", "3", "4"],
        "Coltrane Pattern from 7th (ending on #11)": ["7", "1", "9", "4", "#11"],
    },
    9: {
        "Reverse Minor Coltrane": ["9", "7", "6", "5", "1"],
        "Passing Tone Enclosure": ["9", "4", "9", "#9", "3"],
        "Stan Getz enclosure of II Third": ["9", "#5", "6", "1", "7"],
        "Descending II Scale": ["9", "1", "7", "6", "5"],
        "Descending II Arpeggio from II-5th": ["9", "7", "5", "4", "3"],
    },
    4: {
        "Perfect Chromatic Enclosure of 5th": ["4", "#11", "6", "#5", "5"],
        "Descending Mintor 7th arpeggio from 4th": ["4", "9", "7", "5", "3"],
        "Reverse Coltrane Pattern": ["4", "9", "1", "7", "6"],
    },
    "#11": {
        "Sonny Stitt Enclosure of II Root": ["#11", "6", "#5", "#11", "5"],
        "Circle of 5th Approach": ["#11", "6", "5", "4", "3"],
        "Diminished-to-Dominant": ["#11", "6", "5", "3", "1"],
    },
    6: {
        "Hidden Ideal maj7 Arpeggio to 13th": ["6", "7", "9", "4", "6"],
        "George Coleman minor 7": ["6", "5", "9", "4", "3"],
        "Dominant Turn": ["6", "5", "#11", "5", "1"],
        "Chromatic Passing Tone II Enclosure": ["6", "7", "1", "maj7", "7"],
    },
}

dominant_essential_ending_cells = {
    1: {
        "Hank Mobley": ["7", "2", "6", "5", "1"],
        "Freddie Hubbard": ["9", "4", "3", "9", "1"],
        "Dominant Turn": ["6", "5", "#11", "5", "1"],
        "Dominant 9th Arpeggio": ["3", "5", "7", "9", "1"],
        "Reverse Minor Coltrane": ["9", "7", "6", "5", "1"],
        "Descending Dominant Scale from 5th": ["5", "4", "3", "2", "1"],
        "Diminished-to-Dominant": ["#11", "6", "5", "3", "1"],
    },
    3: {
        "Descending Dominant Scale from 7th ending on 3rd": ["7", "6", "5", "4", "3"],
        "Diatonic Enclosure of 3rd": ["5", "9", "4", "9", "3"],
        "Coltrane Pattern from 7th (ending on 3rd)": ["7", "1", "9", "4", "3"],
        "Passing Tone Enclosure": ["9", "4", "9", "#9", "3"],
        "Ascending II-Minor 7th Arpeggio": ["5", "7", "9", "4", "3"],
        "George Coleman minor 7": ["6", "5", "9", "4", "3"],
        "Circle of 5th Approach": ["#11", "6", "5", "4", "3"],
        "Descending II Arpeggio from II-5th": ["9", "7", "5", "4", "3"],
        "Descending Minor 7th arpeggio from 4th": ["4", "9", "7", "5", "3"],
    },
    5: {
        "Dominant Bebop scale from root": ["1", "maj7", "7", "6", "5"],
        "Stan Getz enclosure of II Root": ["7", "4", "#11", "6", "5"],
        "Sonny Stitt Enclosure of II Root": ["#11", "6", "#5", "#11", "5"],
        "Johnny Griffin Enclosure": ["9", "4", "#11", "6", "5"],  # Mccoy
        "Descending II Scale": ["9", "1", "7", "6", "5"],
    },
    7: {
        "Dominant Bebop Scale from 3rd": ["3", "9", "1", "maj7", "7"],
        "Chromatic Passing Tone II Enclosure": [
            "6",
            "7",
            "1",
            "maj7",
            "7",
        ],  # Mccoy but starting w/ #5-6-7
        "Stan Getz enclosure of II 3rd": ["9", "#5", "6", "1", "7"],
        "Coltrane Pattern from root": ["1", "9", "3", "5", "7"],
    },
    9: {
        "Ascending II Scale": ["5", "6", "7", "1", "9"],
        "Cannonball Adderley Approach": ["5", "4", "3", "4", "9"],
    },
    4: {
        "Ascending Scale from II 3rd": ["7", "1", "9", "3", "4"],
        "Jimmy Heath": ["1", "maj7", "7", "9", "4"],
    },
    "#11": {
        "Coltrane Pattern from 7th (ending on #11)": ["7", "1", "9", "4", "#11"],
        "Descending Dominant Scale from 7th ending on #11": ["7", "6", "5", "4", "#11"],
        "Diatonic Enclosure to #11": ["5", "9", "4", "9", "#11"],
    },
    6: {
        "Ascending II-Minor 7th Arpeggio (ending on 6th)": ["5", "7", "9", "4", "6"],
        "Lee Morgan Dominant": ["1", "maj7", "7", "9", "6"],
        "Minor Honeysuckle Rose": ["1", "7", "9", "4", "6"],
        "Hidden Ideal maj7 Arpeggio to 13th": ["6", "7", "9", "4", "6"],
    },
}
