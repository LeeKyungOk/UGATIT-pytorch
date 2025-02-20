def train(self):
    self.genA2B.train(), self.genB2A.train(), self.disGA.train(), self.disGB.train(), self.disLA.train(), self.disLB.train()

    start_iter = 1

    # === 추가된 부분: iterator 초기화 ===
    trainA_iter = iter(self.trainA_loader)
    trainB_iter = iter(self.trainB_loader)
    testA_iter = iter(self.testA_loader)
    testB_iter = iter(self.testB_loader)
    # === 추가된 부분 끝 ===

    if self.resume:
        model_list = glob(os.path.join(self.result_dir, self.dataset, 'model', '*.pt'))
        if not len(model_list) == 0:
            model_list.sort()
            start_iter = int(model_list[-1].split('_')[-1].split('.')[0])
            self.load(os.path.join(self.result_dir, self.dataset, 'model'), start_iter)
            print(" [*] Load SUCCESS")
            if self.decay_flag and start_iter > (self.iteration // 2):
                self.G_optim.param_groups[0]['lr'] -= (self.lr / (self.iteration // 2)) * (start_iter - self.iteration // 2)
                self.D_optim.param_groups[0]['lr'] -= (self.lr / (self.iteration // 2)) * (start_iter - self.iteration // 2)

    # training loop
    print('training start !')
    start_time = time.time()

    for step in range(start_iter, self.iteration + 1):
        if self.decay_flag and step > (self.iteration // 2):
            self.G_optim.param_groups[0]['lr'] -= (self.lr / (self.iteration // 2))
            self.D_optim.param_groups[0]['lr'] -= (self.lr / (self.iteration // 2))

        try:
            real_A, _ = next(trainA_iter)
        except StopIteration:
            trainA_iter = iter(self.trainA_loader)
            real_A, _ = next(trainA_iter)

        try:
            real_B, _ = next(trainB_iter)
        except StopIteration:
            trainB_iter = iter(self.trainB_loader)
            real_B, _ = next(trainB_iter)

        real_A, real_B = real_A.to(self.device), real_B.to(self.device)

        # Update D
        self.D_optim.zero_grad()

        fake_A2B, _, _ = self.genA2B(real_A)
        fake_B2A, _, _ = self.genB2A(real_B)

        real_GA_logit, real_GA_cam_logit, _ = self.disGA(real_A)
        real_LA_logit, real_LA_cam_logit, _ = self.disLA(real_A)
        real_GB_logit, real_GB_cam_logit, _ = self.disGB(real_B)
        real_LB_logit, real_LB_cam_logit, _ = self.disLB(real_B)

        fake_GA_logit, fake_GA_cam_logit, _ = self.disGA(fake_B2A)
        fake_LA_logit, fake_LA_cam_logit, _ = self.disLA(fake_B2A)
        fake_GB_logit, fake_GB_cam_logit, _ = self.disGB(fake_A2B)
        fake_LB_logit, fake_LB_cam_logit, _ = self.disLB(fake_A2B)

        D_ad_loss_GA = self.MSE_loss(real_GA_logit, torch.ones_like(real_GA_logit).to(self.device)) + self.MSE_loss(fake_GA_logit, torch.zeros_like(fake_GA_logit).to(self.device))
        D_ad_cam_loss_GA = self.MSE_loss(real_GA_cam_logit, torch.ones_like(real_GA_cam_logit).to(self.device)) + self.MSE_loss(fake_GA_cam_logit, torch.zeros_like(fake_GA_cam_logit).to(self.device))
        D_ad_loss_LA = self.MSE_loss(real_LA_logit, torch.ones_like(real_LA_logit).to(self.device)) + self.MSE_loss(fake_LA_logit, torch.zeros_like(fake_LA_logit).to(self.device))
        D_ad_cam_loss_LA = self.MSE_loss(real_LA_cam_logit, torch.ones_like(real_LA_cam_logit).to(self.device)) + self.MSE_loss(fake_LA_cam_logit, torch.zeros_like(fake_LA_cam_logit).to(self.device))
        D_ad_loss_GB = self.MSE_loss(real_GB_logit, torch.ones_like(real_GB_logit).to(self.device)) + self.MSE_loss(fake_GB_logit, torch.zeros_like(fake_GB_logit).to(self.device))
        D_ad_cam_loss_GB = self.MSE_loss(real_GB_cam_logit, torch.ones_like(real_GB_cam_logit).to(self.device)) + self.MSE_loss(fake_GB_cam_logit, torch.zeros_like(fake_GB_cam_logit).to(self.device))
        D_ad_loss_LB = self.MSE_loss(real_LB_logit, torch.ones_like(real_LB_logit).to(self.device)) + self.MSE_loss(fake_LB_logit, torch.zeros_like(fake_LB_logit).to(self.device))
        D_ad_cam_loss_LB = self.MSE_loss(real_LB_cam_logit, torch.ones_like(real_LB_cam_logit).to(self.device)) + self.MSE_loss(fake_LB_cam_logit, torch.zeros_like(fake_LB_cam_logit).to(self.device))

        D_loss_A = self.adv_weight * (D_ad_loss_GA + D_ad_cam_loss_GA + D_ad_loss_LA + D_ad_cam_loss_LA)
        D_loss_B = self.adv_weight * (D_ad_loss_GB + D_ad_cam_loss_GB + D_ad_loss_LB + D_ad_cam_loss_LB)

        Discriminator_loss = D_loss_A + D_loss_B
        Discriminator_loss.backward()
        self.D_optim.step()

        # Update G
        self.G_optim.zero_grad()

        fake_A2B, fake_A2B_cam_logit, _ = self.genA2B(real_A)
        fake_B2A, fake_B2A_cam_logit, _ = self.genB2A(real_B)

        fake_A2B2A, _, _ = self.genB2A(fake_A2B)
        fake_B2A2B, _, _ = self.genA2B(fake_B2A)

        fake_A2A, fake_A2A_cam_logit, _ = self.genB2A(real_A)
        fake_B2B, fake_B2B_cam_logit, _ = self.genA2B(real_B)

        fake_GA_logit, fake_GA_cam_logit, _ = self.disGA(fake_B2A)
        fake_LA_logit, fake_LA_cam_logit, _ = self.disLA(fake_B2A)
        fake_GB_logit, fake_GB_cam_logit, _ = self.disGB(fake_A2B)
        fake_LB_logit, fake_LB_cam_logit, _ = self.disLB(fake_A2B)

        G_ad_loss_GA = self.MSE_loss(fake_GA_logit, torch.ones_like(fake_GA_logit).to(self.device))
        G_ad_cam_loss_GA = self.MSE_loss(fake_GA_cam_logit, torch.ones_like(fake_GA_cam_logit).to(self.device))
        G_ad_loss_LA = self.MSE_loss(fake_LA_logit, torch.ones_like(fake_LA_logit).to(self.device))
        G_ad_cam_loss_LA = self.MSE_loss(fake_LA_cam_logit, torch.ones_like(fake_LA_cam_logit).to(self.device))
        G_ad_loss_GB = self.MSE_loss(fake_GB_logit, torch.ones_like(fake_GB_logit).to(self.device))
        G_ad_cam_loss_GB = self.MSE_loss(fake_GB_cam_logit, torch.ones_like(fake_GB_cam_logit).to(self.device))
        G_ad_loss_LB = self.MSE_loss(fake_LB_logit, torch.ones_like(fake_LB_logit).to(self.device))
        G_ad_cam_loss_LB = self.MSE_loss(fake_LB_cam_logit, torch.ones_like(fake_LB_cam_logit).to(self.device))

        G_recon_loss_A = self.L1_loss(fake_A2B2A, real_A)
        G_recon_loss_B = self.L1_loss(fake_B2A2B, real_B)

        G_identity_loss_A = self.L1_loss(fake_A2A, real_A)
        G_identity_loss_B = self.L1_loss(fake_B2B, real_B)

        G_cam_loss_A = self.BCE_loss(fake_B2A_cam_logit, torch.ones_like(fake_B2A_cam_logit).to(self.device)) + self.BCE_loss(fake_A2A_cam_logit, torch.zeros_like(fake_A2A_cam_logit).to(self.device))
        G_cam_loss_B = self.BCE_loss(fake_A2B_cam_logit, torch.ones_like(fake_A2B_cam_logit).to(self.device)) + self.BCE_loss(fake_B2B_cam_logit, torch.zeros_like(fake_B2B_cam_logit).to(self.device))

        G_loss_A =  self.adv_weight * (G_ad_loss_GA + G_ad_cam_loss_GA + G_ad_loss_LA + G_ad_cam_loss_LA) + self.cycle_weight * G_recon_loss_A + self.identity_weight * G_identity_loss_A + self.cam_weight * G_cam_loss_A
        G_loss_B = self.adv_weight * (G_ad_loss_GB + G_ad_cam_loss_GB + G_ad_loss_LB + G_ad_cam_loss_LB) + self.cycle_weight * G_recon_loss_B + self.identity_weight * G_identity_loss_B + self.cam_weight * G_cam_loss_B

        Generator_loss = G_loss_A + G_loss_B
        Generator_loss.backward()
        self.G_optim.step()

        # clip parameter of AdaILN and ILN, applied after optimizer step
        self.genA2B.apply(self.Rho_clipper)
        self.genB2A.apply(self.Rho_clipper)

        print("[%5d/%5d] time: %4.4f d_loss: %.8f, g_loss: %.8f" % (step, self.iteration, time.time() - start_time, Discriminator_loss, Generator_loss))

        # Print and save samples
        if step % self.print_freq == 0:
            train_sample_num = 5
            test_sample_num = 5
            A2B = np.zeros((self.img_size * 7, 0, 3))
            B2A = np.zeros((self.img_size * 7, 0, 3))

            self.genA2B.eval(), self.genB2A.eval(), self.disGA.eval(), self.disGB.eval(), self.disLA.eval(), self.disLB.eval()
            for _ in range(train_sample_num):
                try:
                    real_A, _ = next(trainA_iter)
                except StopIteration:
                    trainA_iter = iter(self.trainA_loader)
                    real_A, _ = next(trainA_iter)

                try:
                    real_B, _ = next(trainB_iter)
                except StopIteration:
                    trainB_iter = iter(self.trainB_loader)
                    real_B, _ = next(trainB_iter)
                real_A, real_B = real_A.to(self.device), real_B.to(self.device)

                fake_A2B, _, fake_A2B_heatmap = self.genA2B(real_A)
                fake_B2A, _, fake_B2A_heatmap = self.genB2A(real_B)

                fake_A2B2A, _, fake_A2B2A_heatmap = self.genB2A(fake_A2B)
                fake_B2A2B, _, fake_B2A2B_heatmap = self.genA2B(fake_B2A)

                fake_A2A, _, fake_A2A_heatmap = self.genB2A(real_A)
                fake_B2B, _, fake_B2B_heatmap = self.genA2B(real_B)

                A2B = np.concatenate((A2B, np.concatenate((RGB2BGR(tensor2numpy(denorm(real_A[0]))),
                                                           cam(tensor2numpy(fake_A2A_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_A2A[0]))),
                                                           cam(tensor2numpy(fake_A2B_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_A2B[0]))),
                                                           cam(tensor2numpy(fake_A2B2A_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_A2B2A[0])))), 0)), 1)

                B2A = np.concatenate((B2A = np.concatenate((B2A, np.concatenate((RGB2BGR(tensor2numpy(denorm(real_B[0]))),
                                                           cam(tensor2numpy(fake_B2B_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_B2B[0]))),
                                                           cam(tensor2numpy(fake_B2A_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_B2A[0]))),
                                                           cam(tensor2numpy(fake_B2A2B_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_B2A2B[0])))), 0)), 1)

            for _ in range(test_sample_num):
                try:
                    real_A, _ = next(testA_iter)
                except StopIteration:
                    testA_iter = iter(self.testA_loader)
                    real_A, _ = next(testA_iter)

                try:
                    real_B, _ = next(testB_iter)
                except StopIteration:
                    testB_iter = iter(self.testB_loader)
                    real_B, _ = next(testB_iter)
                real_A, real_B = real_A.to(self.device), real_B.to(self.device)

                fake_A2B, _, fake_A2B_heatmap = self.genA2B(real_A)
                fake_B2A, _, fake_B2A_heatmap = self.genB2A(real_B)

                fake_A2B2A, _, fake_A2B2A_heatmap = self.genB2A(fake_A2B)
                fake_B2A2B, _, fake_B2A2B_heatmap = self.genA2B(fake_B2A)

                fake_A2A, _, fake_A2A_heatmap = self.genB2A(real_A)
                fake_B2B, _, fake_B2B_heatmap = self.genA2B(real_B)

                A2B = np.concatenate((A2B, np.concatenate((RGB2BGR(tensor2numpy(denorm(real_A[0]))),
                                                           cam(tensor2numpy(fake_A2A_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_A2A[0]))),
                                                           cam(tensor2numpy(fake_A2B_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_A2B[0]))),
                                                           cam(tensor2numpy(fake_A2B2A_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_A2B2A[0])))), 0)), 1)

                B2A = np.concatenate((B2A, np.concatenate((RGB2BGR(tensor2numpy(denorm(real_B[0]))),
                                                           cam(tensor2numpy(fake_B2B_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_B2B[0]))),
                                                           cam(tensor2numpy(fake_B2A_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_B2A[0]))),
                                                           cam(tensor2numpy(fake_B2A2B_heatmap[0]), self.img_size),
                                                           RGB2BGR(tensor2numpy(denorm(fake_B2A2B[0])))), 0)), 1)

            cv2.imwrite(os.path.join(self.result_dir, self.dataset, 'img', 'A2B_%07d.png' % step), A2B * 255.0)
            cv2.imwrite(os.path.join(self.result_dir, self.dataset, 'img', 'B2A_%07d.png' % step), B2A * 255.0)
            self.genA2B.train(), self.genB2A.train(), self.disGA.train(), self.disGB.train(), self.disLA.train(), self.disLB.train()

        if step % self.save_freq == 0:
            self.save(os.path.join(self.result_dir, self.dataset, 'model'), step)

        if step % 1000 == 0:
            params = {}
            params['genA2B'] = self.genA2B.state_dict()
            params['genB2A'] = self.genB2A.state_dict()
            params['disGA'] = self.disGA.state_dict()
            params['disGB'] = self.disGB.state_dict()
            params['disLA'] = self.disLA.state_dict()
            params['disLB'] = self.disLB.state_dict()
            torch.save(params, os.path.join(self.result_dir, self.dataset + '_params_latest.pt'))