import unittest
from unittest.mock import MagicMock, patch, Mock
from music import Music_Manager, Song, song_from_youtube

class TestMusicManager(unittest.TestCase):

    def setUp(self):
        # Create a mock voice client
        self.mock_voice_client = MagicMock()
        self.mock_voice_client.is_playing.return_value = False
        self.mock_voice_client.is_paused.return_value = False
        self.mock_voice_client.is_connected.return_value = True

        # Create music manager instance
        self.manager = Music_Manager(self.mock_voice_client)

    def test_request_song(self):
        """Test that request_song adds song to queue and plays if nothing is playing"""
        # Mock the song_from_youtube function
        mock_song = Mock(spec=Song)
        mock_song.name = "Test Song"
        mock_song.filename = "test_song.mp3"
        mock_song.url = "https://example.com/test"

        with patch('music.song_from_youtube', return_value=mock_song):
            # Initially nothing is playing
            self.manager.request_song("Test Song")
            self.assertFalse(self.manager.current_queue.empty())
            self.mock_voice_client.play.assert_called()

    def test_play_next_with_queue(self):
        """Test play_next with songs in queue"""
        # Add multiple songs to queue
        song1 = Mock(spec=Song)
        song1.name = "Song 1"
        song1.filename = "song1.mp3"

        song2 = Mock(spec=Song)
        song2.name = "Song 2"
        song2.filename = "song2.mp3"

        self.manager.current_queue.put(song1)
        self.manager.current_queue.put(song2)

        # Play first song
        self.manager.play_next()
        self.assertEqual(self.manager.current_song, song1)

        # Play second song
        self.manager.play_next()
        self.assertEqual(self.manager.current_song, song2)

    def test_play_next_with_empty_queue(self):
        """Test play_next with empty queue and autoplay"""
        # Mock autoplay functionality
        autoplay_song = Mock(spec=Song)
        autoplay_song.name = "Autoplay Song"
        autoplay_song.filename = "autoplay.mp3"

        # Mock the autoplay song creation
        with patch.object(self.manager, '_create_autoplay_song') as mock_create:
            mock_create.return_value = autoplay_song
            self.manager.potential_autoplay = autoplay_song

            self.manager.play_next()
            self.assertEqual(self.manager.current_song, autoplay_song)

    def test_pause_and_resume(self):
        """Test pause and resume functionality"""
        self.manager.pause()
        self.mock_voice_client.pause.assert_called_once()

        self.manager.resume()
        self.mock_voice_client.resume.assert_called_once()

    def test_voice_client_update(self):
        """Test updating voice client"""
        new_voice_client = MagicMock()
        self.manager.update_voice_client(new_voice_client)
        self.assertEqual(self.manager.voice_client, new_voice_client)

    def test_song_history(self):
        """Test that songs are added to history when played"""
        song = Mock(spec=Song)
        song.name = "History Song"

        # Mock the play method
        with patch.object(self.manager, '_play_song') as mock_play:
            mock_play.return_value = None
            self.manager._play_song(song)

        self.assertIn("History Song", self.manager.song_history)

    def test_autoplay_creation(self):
        """Test autoplay song creation"""
        # Mock the recommendation function
        mock_recommendations = ["Recommendation 1", "Recommendation 2"]
        with patch('music.spotify_reccomendation', return_value=mock_recommendations):
            with patch('music.song_from_youtube', return_value=Mock(spec=Song)) as mock_song:
                self.manager._create_autoplay_song()
                self.assertIsNotNone(self.manager.potential_autoplay)

    def test_queue_management(self):
        """Test queue management and song transitions"""
        # Add songs to queue
        song1 = Mock(spec=Song)
        song1.name = "Song 1"

        song2 = Mock(spec=Song)
        song2.name = "Song 2"

        self.manager.current_queue.put(song1)
        self.manager.current_queue.put(song2)

        # Play first song
        self.manager.play_next()
        self.assertEqual(self.manager.current_song, song1)

        # Play second song
        self.manager.play_next()
        self.assertEqual(self.manager.current_song, song2)

        # Queue should be empty
        self.assertTrue(self.manager.current_queue.empty())

    def test_voice_client_disconnection(self):
        """Test behavior when voice client disconnects"""
        # Mock disconnection
        self.mock_voice_client.is_connected.return_value = False

        # Should not play anything
        self.manager.play_next()
        self.assertIsNone(self.manager.current_song)

if __name__ == '__main__':
    unittest.main()