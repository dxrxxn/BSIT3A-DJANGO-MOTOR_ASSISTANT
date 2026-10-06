-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Oct 06, 2026 at 03:48 AM
-- Server version: 10.4.28-MariaDB
-- PHP Version: 8.2.4

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `motor_assistant_db`
--

-- --------------------------------------------------------

--
-- Table structure for table `diagnostic_symptoms`
--

CREATE TABLE `diagnostic_symptoms` (
  `id` int(11) NOT NULL,
  `symptom_name` varchar(150) NOT NULL,
  `category` varchar(50) NOT NULL,
  `description` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `diagnostic_symptoms`
--

INSERT INTO `diagnostic_symptoms` (`id`, `symptom_name`, `category`, `description`, `created_at`) VALUES
(1, 'Smoke near engine and front sprocket', 'Engine', 'White or gray smoke issuing near the front sprocket area after riding.', '2026-10-06 01:45:19');

-- --------------------------------------------------------

--
-- Table structure for table `guide_required_parts`
--

CREATE TABLE `guide_required_parts` (
  `id` int(11) NOT NULL,
  `guide_id` int(11) NOT NULL,
  `part_id` int(11) NOT NULL,
  `quantity_needed` int(11) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `guide_required_parts`
--

INSERT INTO `guide_required_parts` (`id`, `guide_id`, `part_id`, `quantity_needed`) VALUES
(1, 1, 1, 1);

-- --------------------------------------------------------

--
-- Table structure for table `parts`
--

CREATE TABLE `parts` (
  `id` int(11) NOT NULL,
  `part_name` varchar(100) NOT NULL,
  `part_number` varchar(50) DEFAULT NULL,
  `category` varchar(50) DEFAULT NULL,
  `estimated_cost` decimal(10,2) DEFAULT 0.00,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `parts`
--

INSERT INTO `parts` (`id`, `part_name`, `part_number`, `category`, `estimated_cost`, `created_at`) VALUES
(1, 'Front Sprocket Oil Seal', 'OS-17-29-6', 'Engine Seals', 150.00, '2026-10-06 01:45:19');

-- --------------------------------------------------------

--
-- Table structure for table `troubleshooting_guides`
--

CREATE TABLE `troubleshooting_guides` (
  `id` int(11) NOT NULL,
  `symptom_id` int(11) NOT NULL,
  `possible_cause` varchar(255) NOT NULL,
  `repair_instructions` text NOT NULL,
  `advice_notes` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `troubleshooting_guides`
--

INSERT INTO `troubleshooting_guides` (`id`, `symptom_id`, `possible_cause`, `repair_instructions`, `advice_notes`, `created_at`) VALUES
(1, 1, 'Leaking front sprocket oil seal dripping onto hot engine casing/exhaust', '1. Remove shift lever and sprocket cover.\n2. Clean oil grime using engine degreaser.\n3. Remove chain and front sprocket.\n4. Pry out damaged oil seal carefully.\n5. Install new oil seal flush with casing.\n6. Reassemble sprocket and chain.', 'Check engine oil level immediately to prevent engine starvation.', '2026-10-06 01:45:19');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `id` int(11) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `email` varchar(100) NOT NULL,
  `role` varchar(20) DEFAULT 'Mechanic',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Indexes for dumped tables
--

--
-- Indexes for table `diagnostic_symptoms`
--
ALTER TABLE `diagnostic_symptoms`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `guide_required_parts`
--
ALTER TABLE `guide_required_parts`
  ADD PRIMARY KEY (`id`),
  ADD KEY `guide_id` (`guide_id`),
  ADD KEY `part_id` (`part_id`);

--
-- Indexes for table `parts`
--
ALTER TABLE `parts`
  ADD PRIMARY KEY (`id`);

--
-- Indexes for table `troubleshooting_guides`
--
ALTER TABLE `troubleshooting_guides`
  ADD PRIMARY KEY (`id`),
  ADD KEY `symptom_id` (`symptom_id`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `email` (`email`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `diagnostic_symptoms`
--
ALTER TABLE `diagnostic_symptoms`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `guide_required_parts`
--
ALTER TABLE `guide_required_parts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `parts`
--
ALTER TABLE `parts`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `troubleshooting_guides`
--
ALTER TABLE `troubleshooting_guides`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=2;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `guide_required_parts`
--
ALTER TABLE `guide_required_parts`
  ADD CONSTRAINT `guide_required_parts_ibfk_1` FOREIGN KEY (`guide_id`) REFERENCES `troubleshooting_guides` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `guide_required_parts_ibfk_2` FOREIGN KEY (`part_id`) REFERENCES `parts` (`id`) ON DELETE CASCADE;

--
-- Constraints for table `troubleshooting_guides`
--
ALTER TABLE `troubleshooting_guides`
  ADD CONSTRAINT `troubleshooting_guides_ibfk_1` FOREIGN KEY (`symptom_id`) REFERENCES `diagnostic_symptoms` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
